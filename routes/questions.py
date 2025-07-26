# routes/questions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime
import uuid

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


load_dotenv()
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client["math_edu_db"]

router = APIRouter(prefix="/api/questions", tags=["questions"])

# Define segment model
class Segment(BaseModel):
    value: str
    type: str = Field(..., pattern="^(text|latex|newline)$")  # Updated to include "newline"
    original_latex: Optional[str] = None

# Updated Question model
class Question(BaseModel):
    title: str
    content: str
    question: List[Segment] = []  # Array of segments
    category: Optional[str] = None
    difficulty: str
    knowledgePointIds: List[str] = []  # List of knowledge point IDs
    correctAnswer: List[Segment] = []  # Array of answer segments
    passValidation: Optional[bool] = False
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    isActive: bool = True
    id: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "title": "Sample Question",
                "question": [
                    {"value": "Solve the equation ", "type": "text", "original_latex": None},
                    {"value": "x + 2 = 5", "type": "latex", "original_latex": "$x + 2 = 5$"},
                    {"value": "", "type": "newline", "original_latex": None}
                ],
                "category": "algebra",
                "difficulty": "easy",
                "knowledgePointIds": ["kp1", "kp2"],
                "correctAnswer": [{"value": "x=3", "type": "latex", "original_latex": "$x=3$"}],
                "passValidation": False
            }
        }

class QuestionResponse(BaseModel):
    id: str
    title: str
    #content: List[Segment] = None  # Array of segments
    question: List[Segment] = []  # Array of segments
    category: Optional[str] = None
    difficulty: str
    knowledgePoints: List[dict]  # Expanded knowledge points
    correctAnswer: List[Segment]  # Array of answer segments
    passValidation: Optional[bool] = False
    createdAt: str
    updatedAt: str
    isActive: bool


@router.post("/", response_model=QuestionResponse)
async def add_question(question: Question):
    # Temporarily disable validation for empty question list
    # if not question.question or not any(seg.value.strip() for seg in question.question):
    #     raise HTTPException(status_code=422, detail="Question must contain at least one non-empty segment")

    logger.info(f"question:{question}")

    # Validate knowledge point IDs
    valid_points = await db.knowledge_points.find(
        {"id": {"$in": question.knowledgePointIds}, "isActive": True}
    ).to_list(None)
    if len(valid_points) != len(question.knowledgePointIds):
        raise HTTPException(400, "Some knowledge point IDs are invalid or inactive")

    # log valid_points content
    logger.info(f"Valid knowledge points: {valid_points}")

    question_dict = question.dict(exclude={"id"})
    question_dict["content"] = question.content
    question_dict["id"] = str(uuid.uuid4())
    #question_dict["knowledgePointIds"] = question.knowledgePointIds  # Store UUIDs
    question_dict["createdAt"] = datetime.utcnow().isoformat()
    question_dict["updatedAt"] = datetime.utcnow().isoformat()
    question_dict["isActive"] = True

    # log question.question content
    logger.info(f"Question content: {question.question}")   
    logger.info(f"question_dict question: {question_dict['question']}")   
    
    # if question_dict["question"] is not None and first segment is a newline, remove it
    if question_dict["question"] and question_dict["question"][0].get("type") == "newline":
        question_dict["question"] = question_dict["question"][1:]

    
    # if question.question is not empty and first segment is a newline, remove it
    #if question.question and question.question[0].type == "newline":
    #    question_dict["question"] = question.question[1:]
    #else:
    #    question_dict["question"] = question.question   

    await db.questions.insert_one(question_dict)
    question_dict["knowledgePoints"] = [
        {
            "id": p["id"],
            "grade": p["grade"],
            "strand": p["strand"],
            "topic": p["topic"],
            "skill": p["skill"],
            "subKnowledgePoint": p["subKnowledgePoint"]
        }
        for p in valid_points
    ]
    return question_dict

@router.get("/", response_model=List[QuestionResponse])
async def get_questions():
    questions = await db.questions.find({"isActive": True}).to_list(None)
    for question in questions:
        logger.info(f"Processing question: {question}")
        question["knowledgePointIds"] = await db.knowledge_points.find(
            {"id": {"$in": question["knowledgePointIds"]}, "isActive": True}
        ).to_list(None)
        question["knowledgePoints"] = [
            {
                "id": p["id"],
                "grade": p["grade"],
                "strand": p["strand"],
                "topic": p["topic"],
                "skill": p["skill"],
                "subKnowledgePoint": p["subKnowledgePoint"]
            }
            for p in question["knowledgePointIds"]
        ]
        # Provide default values for optional fields if missing
        question["correctAnswer"] = question.get("correctAnswer", [])
        question["passValidation"] = question.get("passValidation", False)
        # Ensure question is a list of segments if it was stored as a string
        if isinstance(question.get("question"), str):
            from latex_parser import parse_mixed_content_with_original
            question["question"] = parse_mixed_content_with_original(question["question"])
        # Ensure correctAnswer is a list of segments if it was stored as a string
        if isinstance(question.get("correctAnswer"), str):
            question["correctAnswer"] = [
                {"value": seg.strip(), "type": "latex", "original_latex": seg.strip()}
                for seg in question["correctAnswer"].split(",")
            ]
    return questions

@router.get("/{id}/", response_model=QuestionResponse)
async def get_question_by_id(id: str):
    try:
        question = await db.questions.find_one({"id": id, "isActive": True})
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        question["knowledgePoints"] = await db.knowledge_points.find(
            {"id": {"$in": question["knowledgePoints"]}, "isActive": True}
        ).to_list(None)
        question["knowledgePoints"] = [
            {
                "id": p["id"],
                "grade": p["grade"],
                "strand": p["strand"],
                "topic": p["topic"],
                "skill": p["skill"],
                "subKnowledgePoint": p["subKnowledgePoint"]
            }
            for p in question["knowledgePoints"]
        ]
        # Provide default values for optional fields if missing
        question["correctAnswer"] = question.get("correctAnswer", [])
        question["passValidation"] = question.get("passValidation", False)
        # Ensure question is a list of segments if it was stored as a string
        if isinstance(question.get("question"), str):
            from latex_parser import parse_mixed_content_with_original
            question["question"] = parse_mixed_content_with_original(question["question"])
        # Ensure correctAnswer is a list of segments if it was stored as a string
        if isinstance(question.get("correctAnswer"), str):
            question["correctAnswer"] = [
                {"value": seg.strip(), "type": "latex", "original_latex": seg.strip()}
                for seg in question["correctAnswer"].split(",")
            ]
        return question
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching question: {str(e)}")
