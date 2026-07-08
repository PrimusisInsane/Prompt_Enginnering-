import json
from ariadne import QueryType, MutationType, make_executable_schema, gql
from sqlalchemy import select
from app.services.generation import get_cached_or_generate_bark
from app.services.storage import save_bark_generation
from app.db import async_session
from app.models import Generation


type_defs = gql("""
    type Query {
        hello: String!
        generations: [GenerationRecord!]!
    }

    type Mutation {
        generateBark(enemyType: String!): BarkResult!
    }

    type BarkResult {
        id: Int!
        contentType: String!
        enemyType: String!
        lines: [String!]!
        createdAt: String!
    }

    type GenerationRecord {
        id: Int!
        contentType: String!
        promptInput: String!
        generatedOutput: String!
        createdAt: String!
    }
""")

query = QueryType()
mutation = MutationType()


@query.field("hello")
def resolve_hello(_, info):
    return "GraphQL is wired up"


@query.field("generations")
async def resolve_generations(_, info):
    async with async_session() as session:
        result = await session.execute(
            select(Generation).order_by(Generation.created_at.desc())
        )
        records = result.scalars().all()

    return [
        {
            "id": r.id,
            "contentType": r.content_type,
            "promptInput": r.prompt_input,
            "generatedOutput": r.generated_output,
            "createdAt": r.created_at.isoformat(),
        }
        for r in records
    ]


@mutation.field("generateBark")
async def resolve_generate_bark(_, info, enemyType: str):
    prompt_input = f"Generate bark lines for enemy_type: {enemyType}"

    validated, was_cached = await get_cached_or_generate_bark(enemyType, prompt_input)

    async with async_session() as session:
        record = await save_bark_generation(session, prompt_input, validated)

    return {
        "id": record.id,
        "contentType": record.content_type,
        "enemyType": validated.enemy_type,
        "lines": validated.lines,
        "createdAt": record.created_at.isoformat(),
    }

schema = make_executable_schema(type_defs, query, mutation)