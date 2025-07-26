# main.py
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import verify_answer, question_generator, ai_mistral,ai_grok, questions, assignments, answers, auth, users, classrooms, performance, managers, knowledge_points, courses, tutors, students, google_auth
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client["math_edu_db"]

async def init_db():
    await db.users.create_index("id", unique=True)
    await db.assignments.create_index("id", unique=True)
    await db.classrooms.create_index("id", unique=True)
    await db.courses.create_index("id", unique=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions.router)
app.include_router(users.router)
app.include_router(assignments.router)
app.include_router(ai_grok.router)
app.include_router(ai_mistral.router)
app.include_router(answers.router)
app.include_router(auth.router)
app.include_router(classrooms.router)
app.include_router(performance.router)
app.include_router(managers.router)
app.include_router(knowledge_points.router)
app.include_router(courses.router)
app.include_router(tutors.router)
app.include_router(students.router)
app.include_router(verify_answer.router)
app.include_router(question_generator.router)
app.include_router(google_auth.router)



@app.on_event("startup")
async def startup_event():
    await init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)