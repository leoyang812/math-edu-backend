# routes/users.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bcrypt import hashpw, gensalt
import os
from dotenv import load_dotenv
from .auth import get_current_user
import logging
from pymongo.errors import DuplicateKeyError
from typing import Optional, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client["math_edu_db"]

router = APIRouter(prefix="/api/users", tags=["users"])

class UserCreate(BaseModel):
    id: str
    name: str
    email: str
    password: str
    role: str
    language: str = "en"
    tutorId: Optional[str] = None
    studentIds: List[str] = []
    parentIds: List[str] = []
    classroomIds: List[str] = []
    disabled: bool = False

class PublicSignup(BaseModel):
    name: str
    email: str
    password: str
    language: str = "en"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    language: Optional[str] = "en"
    tutorId: Optional[str] = None
    studentIds: List[str] = []
    parentIds: List[str] = []
    classroomIds: List[str] = []
    disabled: Optional[bool] = None

class AssignParent(BaseModel):
    studentId: str
    parentIds: List[str]

class AssignStudent(BaseModel):
    parentId: str
    studentIds: List[str]

class AssignTutorStudents(BaseModel):
    tutorId: str
    studentIds: List[str]

VALID_ROLES = {"student", "parent", "tutor", "manager", "admin"}

async def validate_user_ids(user_ids: List[str], role: str, field: str) -> None:
    """Validate that all user IDs exist and match the specified role."""
    for user_id in user_ids:
        user = await db.users.find_one({"id": user_id, "role": role, "disabled": False})
        if not user:
            raise HTTPException(status_code=400, detail=f"{role.capitalize()} not found for {field}: {user_id}")

@router.get("/")
async def get_users(
    role: str = None, 
    include_disabled: bool = False, 
    search: str = None, 
    page: int = 1, 
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    logger.info(f"Fetching users with role={role}, search={search}, page={page}, limit={limit}, current_user={current_user['id']}")
    if role and role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {', '.join(VALID_ROLES)}")
    
    query = {"role": role} if role else {}
    if not include_disabled:
        query["disabled"] = False
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    total = await db.users.count_documents(query)
    users = await db.users.find(query).skip((page - 1) * limit).limit(limit).to_list(None)
    return {
        "users": [
            {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "language": user["language"],
                "tutorId": user.get("tutorId"),
                "studentIds": user.get("studentIds", []),
                "parentIds": user.get("parentIds", []),
                "classroomIds": user.get("classroomIds", []),
                "disabled": user.get("disabled", False)
            }
            for user in users
        ],
        "total": total
    }

@router.get("/bytutor/{tutor_id}")
async def get_users_by_tutor(tutor_id: str, current_user: dict = Depends(get_current_user)):
    logger.info(f"Fetching users for tutor_id: {tutor_id}, current_user: {current_user['id']}")
    if current_user["role"] not in ["tutor"]:
        raise HTTPException(status_code=403, detail="Unauthorized access")
    
    query = {"tutorId": tutor_id, "disabled": False}
    users = await db.users.find(query).to_list(None)
    return [
        {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "language": user["language"],
            "tutorId": user.get("tutorId"),
            "studentIds": user.get("studentIds", []),
            "parentIds": user.get("parentIds", []),
            "classroomIds": user.get("classroomIds", [])
        }
        for user in users
    ]

@router.get("/children/pid={parent_id}")
async def get_children_by_parent(parent_id: str, current_user: dict = Depends(get_current_user)):
    logger.info(f"Fetching children for parent_id: {parent_id}, current_user: {current_user['id']}")
    if current_user["role"] not in ["parent"]:
        raise HTTPException(status_code=403, detail="Unauthorized access")
    
    if current_user["id"] != parent_id:
        raise HTTPException(status_code=403, detail="Cannot access another parent's children")
    
    children = []
    if "studentIds" in current_user and current_user["studentIds"]:
        children = await db.users.find({"id": {"$in": current_user["studentIds"]}, "role": "student", "disabled": False}).to_list(None)
    
    return [
        {
            "id": child["id"],
            "name": child["name"],
            "email": child["email"],
            "language": child["language"]
        }
        for child in children
    ]

@router.post("/")
async def add_user(user: UserCreate, current_user: dict = Depends(get_current_user)):
    logger.info(f"Adding user: {user.id}, role: {user.role}, current_user: {current_user['id']}")
    #if current_user["role"] != "admin":
     #   raise HTTPException(status_code=403, detail="Only admins can add users")
    
    if await db.users.find_one({"id": user.id}):
        raise HTTPException(status_code=400, detail="User ID already exists")
    
    if user.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {', '.join(VALID_ROLES)}")
    
    if user.role == "student" and user.tutorId:
        tutor = await db.users.find_one({"id": user.tutorId, "role": "tutor", "disabled": False})
        if not tutor:
            raise HTTPException(status_code=400, detail="Tutor not found")
    if user.role == "student" and user.parentIds:
        await validate_user_ids(user.parentIds, "parent", "parentIds")
    if user.role == "parent" and user.studentIds:
        await validate_user_ids(user.studentIds, "student", "studentIds")
    
    try:
        hashed_password = hashpw(user.password.encode("utf-8"), gensalt()).decode("utf-8")
        user_dict = user.dict()
        user_dict["password"] = hashed_password
        user_dict["performanceData"] = {"totalCorrect": 0, "totalAttempts": 0, "avgTimeTaken": 0.0}
        await db.users.insert_one(user_dict)
        
        if user.role == "student" and user.tutorId:
            await db.users.update_one(
                {"id": user.tutorId},
                {"$addToSet": {"studentIds": user.id}}
            )
        if user.role == "student" and user.parentIds:
            for parent_id in user.parentIds:
                await db.users.update_one(
                    {"id": parent_id},
                    {"$addToSet": {"studentIds": user.id}}
                )
        if user.role == "parent" and user.studentIds:
            for student_id in user.studentIds:
                await db.users.update_one(
                    {"id": student_id},
                    {"$addToSet": {"parentIds": user.id}}
                )
        
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "language": user.language,
            "tutorId": user.tutorId,
            "studentIds": user.studentIds,
            "parentIds": user.parentIds,
            "classroomIds": user.classroomIds,
            "disabled": user.disabled
        }
    except DuplicateKeyError as e:
        raise HTTPException(status_code=400, detail=f"Duplicate key error: {str(e)}")

@router.put("/{user_id}")
async def update_user(user_id: str, update_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    logger.info(f"Updating user {user_id} with data: {update_data.dict()}, current_user: {current_user['id']}")
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update users")
    
    if update_data.role and update_data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {', '.join(VALID_ROLES)}")
    
    if update_data.role == "student" and update_data.tutorId:
        tutor = await db.users.find_one({"id": update_data.tutorId, "role": "tutor", "disabled": False})
        if not tutor:
            raise HTTPException(status_code=400, detail="Tutor not found")
    if update_data.role == "student" and update_data.parentIds:
        await validate_user_ids(update_data.parentIds, "parent", "parentIds")
    if update_data.role == "parent" and update_data.studentIds:
        await validate_user_ids(update_data.studentIds, "student", "studentIds")
    
    existing_user = await db.users.find_one({"id": user_id, "disabled": False})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found or disabled")
    
    update_dict = update_data.dict(exclude_unset=True)
    update_dict.setdefault("name", existing_user["name"])
    update_dict.setdefault("email", existing_user["email"])
    update_dict.setdefault("role", existing_user["role"])
    
    result = await db.users.update_one(
        {"id": user_id, "disabled": False},
        {"$set": update_dict}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found or no changes made")
    
    if update_data.role == "student" and "parentIds" in update_dict:
        current_parent_ids = existing_user.get("parentIds", [])
        new_parent_ids = update_dict.get("parentIds", [])
        removed_parent_ids = [pid for pid in current_parent_ids if pid not in new_parent_ids]
        for parent_id in removed_parent_ids:
            await db.users.update_one(
                {"id": parent_id},
                {"$pull": {"studentIds": user_id}}
            )
        for parent_id in new_parent_ids:
            await db.users.update_one(
                {"id": parent_id},
                {"$addToSet": {"studentIds": user_id}}
            )
    if update_data.role == "parent" and "studentIds" in update_dict:
        current_student_ids = existing_user.get("studentIds", [])
        new_student_ids = update_dict.get("studentIds", [])
        removed_student_ids = [sid for sid in current_student_ids if sid not in new_student_ids]
        for student_id in removed_student_ids:
            await db.users.update_one(
                {"id": student_id},
                {"$pull": {"parentIds": user_id}}
            )
        for student_id in new_student_ids:
            await db.users.update_one(
                {"id": student_id},
                {"$addToSet": {"parentIds": user_id}}
            )
    
    return {"message": "User updated"}

@router.post("/assign-parent")
async def assign_parent(assignment: AssignParent, current_user: dict = Depends(get_current_user)):
    logger.info(f"Assigning parents to student {assignment.studentId}: {assignment.parentIds}, current_user: {current_user['id']}")
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign parents")
    
    student = await db.users.find_one({"id": assignment.studentId, "role": "student", "disabled": False})
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found: {assignment.studentId}")
    
    await validate_user_ids(assignment.parentIds, "parent", "parentIds")
    
    await db.users.update_one(
        {"id": assignment.studentId},
        {"$set": {"parentIds": assignment.parentIds}}
    )
    
    current_parent_ids = student.get("parentIds", [])
    new_parent_ids = assignment.parentIds
    removed_parent_ids = [pid for pid in current_parent_ids if pid not in new_parent_ids]
    
    for parent_id in removed_parent_ids:
        await db.users.update_one(
            {"id": parent_id},
            {"$pull": {"studentIds": assignment.studentId}}
        )
    
    for parent_id in new_parent_ids:
        await db.users.update_one(
            {"id": parent_id},
            {"$addToSet": {"studentIds": assignment.studentId}}
        )
    
    return {"message": "Parent assigned successfully"}

@router.post("/assign-student")
async def assign_student(assignment: AssignStudent, current_user: dict = Depends(get_current_user)):
    logger.info(f"Assigning students to parent {assignment.parentId}: {assignment.studentIds}, current_user: {current_user['id']}")
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign students")
    
    parent = await db.users.find_one({"id": assignment.parentId, "role": "parent", "disabled": False})
    if not parent:
        raise HTTPException(status_code=404, detail=f"Parent not found: {assignment.parentId}")
    
    await validate_user_ids(assignment.studentIds, "student", "studentIds")
    
    await db.users.update_one(
        {"id": assignment.parentId},
        {"$set": {"studentIds": assignment.studentIds}}
    )
    
    current_student_ids = parent.get("studentIds", [])
    new_student_ids = assignment.studentIds
    removed_student_ids = [sid for sid in current_student_ids if sid not in new_student_ids]
    
    for student_id in removed_student_ids:
        await db.users.update_one(
            {"id": student_id},
            {"$pull": {"parentIds": assignment.parentId}}
        )
    
    for student_id in new_student_ids:
        await db.users.update_one(
            {"id": student_id},
            {"$addToSet": {"parentIds": assignment.parentId}}
        )
    
    return {"message": "Student assigned successfully"}

@router.post("/assign-tutor-students")
async def assign_tutor_students(assignment: AssignTutorStudents, current_user: dict = Depends(get_current_user)):
    logger.info(f"Assigning students to tutor {assignment.tutorId}: {assignment.studentIds}, current_user: {current_user['id']}")
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign students")
    
    tutor = await db.users.find_one({"id": assignment.tutorId, "role": "tutor", "disabled": False})
    if not tutor:
        raise HTTPException(status_code=404, detail=f"Tutor not found: {assignment.tutorId}")
    
    await validate_user_ids(assignment.studentIds, "student", "studentIds")
    
    await db.users.update_one(
        {"id": assignment.tutorId},
        {"$set": {"studentIds": assignment.studentIds}}
    )
    
    current_student_ids = tutor.get("studentIds", [])
    new_student_ids = assignment.studentIds
    removed_student_ids = [sid for sid in current_student_ids if sid not in new_student_ids]
    
    for student_id in removed_student_ids:
        await db.users.update_one(
            {"id": student_id},
            {"$set": {"tutorId": null}}
        )
    
    for student_id in new_student_ids:
        await db.users.update_one(
            {"id": student_id},
            {"$set": {"tutorId": assignment.tutorId}}
        )
    
    return {"message": "Students assigned successfully"}

@router.delete("/{user_id}")
async def soft_delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    logger.info(f"Soft deleting user {user_id}, current_user: {current_user['id']}")
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete users")
    
    user = await db.users.find_one({"id": user_id, "disabled": False})
    if not user:
        raise HTTPException(status_code=404, detail="User not found or already disabled")
    
    if user["role"] == "student" and user.get("tutorId"):
        await db.users.update_one(
            {"id": user["tutorId"]},
            {"$pull": {"studentIds": user_id}}
        )
    if user["role"] == "student" and user.get("parentIds"):
        for parent_id in user["parentIds"]:
            await db.users.update_one(
                {"id": parent_id},
                {"$pull": {"studentIds": user_id}}
            )
    if user["role"] == "parent" and user.get("studentIds"):
        for student_id in user["studentIds"]:
            await db.users.update_one(
                {"id": student_id},
                {"$pull": {"parentIds": user_id}}
            )
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"disabled": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found or no changes made")
    
    return {"message": "User soft deleted"}

@router.post("/signup")
async def public_signup(user: PublicSignup):
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate unique user ID
    import uuid
    user_id = str(uuid.uuid4())
    
    # Set default role to student
    role = "student"

    hashed_password = hashpw(user.password.encode("utf-8"), gensalt()).decode("utf-8")
    user_dict = {
        "id": user_id,
        "name": user.name,
        "email": user.email,
        "password": hashed_password,
        "role": role,
        "language": user.language,
        "tutorId": None,
        "studentIds": [],
        "parentIds": [],
        "classroomIds": [],
        "disabled": False,
        "performanceData": {
            "totalCorrect": 0,
            "totalAttempts": 0,
            "avgTimeTaken": 0.0,
        }
    }
    await db.users.insert_one(user_dict)

    return {"message": "User created successfully", "user_id": user_id}
