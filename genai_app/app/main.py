from fastapi import FastAPI
from ariadne.asgi import GraphQL
from fastapi.middleware.cors import CORSMiddleware
from app.graphql_schema import schema
from app.config import settings

app = FastAPI(title="genai-app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.mount("/graphql", GraphQL(schema, debug=True))
