"""The fixed catalog for the supported application type: a three-tier web application."""
from __future__ import annotations

from ..models import DecisionOption

APP_TYPE_TOPIC = "Application type"
CLIENT_TOPIC = "Web client framework"
SERVER_TOPIC = "API server stack"
ORM_TOPIC = "ORM"
DATABASE_TOPIC = "Database"

THREE_TIER = "Three-tier web application: web client, API server, and a data tier reached through an ORM"

CLIENT_OPTIONS = [
    DecisionOption(
        name="Angular",
        description="TypeScript framework with routing, forms, dependency injection and HTTP built in",
        pros=["Opinionated structure suits large teams", "Batteries included, little library choice to make"],
        cons=["Steeper learning curve", "More boilerplate than React"],
    ),
    DecisionOption(
        name="React",
        description="TypeScript with React; flexible component library with a large ecosystem",
        pros=["Large ecosystem and hiring pool", "Flexible, easy to start small"],
        cons=["Routing, forms and state need extra libraries", "Less enforced structure"],
    ),
]

SERVER_OPTIONS = [
    DecisionOption(
        name="Node.js with TypeScript (NestJS)",
        description="TypeScript API server with NestJS modules, controllers and services",
        pros=["Same language as the web client", "Fast to build, strong typing with TypeScript"],
        cons=["Weaker for CPU-heavy work", "Dependency churn in the npm ecosystem"],
    ),
    DecisionOption(
        name="Python (FastAPI)",
        description="Python API server with FastAPI, Pydantic validation and automatic OpenAPI docs",
        pros=["Concise code and quick iteration", "Strong data and AI library ecosystem"],
        cons=["Slower raw performance than Java", "Needs care with typing and async"],
    ),
    DecisionOption(
        name="Java (Spring Boot)",
        description="Java API server with Spring Boot, Spring Web and Spring Data",
        pros=["Mature, strong typing and tooling", "Well suited to large enterprise systems"],
        cons=["More verbose", "Heavier startup and memory use"],
    ),
]

ORM_OPTIONS = {
    "Node.js with TypeScript (NestJS)": [
        DecisionOption(
            name="Prisma",
            description="Schema-first ORM with generated, fully typed client and migrations",
            pros=["Excellent type safety", "Simple migrations"],
            cons=["Less flexible for unusual SQL", "Generated client adds a build step"],
        ),
        DecisionOption(
            name="TypeORM",
            description="Decorator-based ORM with entities, repositories and migrations",
            pros=["Integrates naturally with NestJS", "Active record or data mapper patterns"],
            cons=["Weaker typing in queries", "Known rough edges in complex relations"],
        ),
    ],
    "Python (FastAPI)": [
        DecisionOption(
            name="SQLAlchemy",
            description="The standard Python ORM with Alembic migrations",
            pros=["Mature and very flexible", "Fine control over SQL"],
            cons=["Steeper learning curve"],
        ),
    ],
    "Java (Spring Boot)": [
        DecisionOption(
            name="Hibernate (Spring Data JPA)",
            description="JPA entities and repositories on Hibernate, with Flyway or Liquibase migrations",
            pros=["Standard in the Java ecosystem", "Repositories need little code"],
            cons=["Can hide inefficient queries (N+1)"],
        ),
    ],
}

DATABASE_OPTIONS = [
    DecisionOption(
        name="PostgreSQL",
        description="Open-source relational database",
        pros=["Rich features and JSON support", "No license cost, runs everywhere"],
        cons=["Needs tuning at very large scale"],
    ),
    DecisionOption(
        name="MySQL",
        description="Open-source relational database",
        pros=["Widely deployed and well understood", "Good managed-service support"],
        cons=["Fewer advanced features than PostgreSQL"],
    ),
    DecisionOption(
        name="SQL Server",
        description="Microsoft relational database",
        pros=["Strong tooling and Azure integration", "Mature enterprise features"],
        cons=["License cost", "Heavier to run outside Windows and Azure"],
    ),
]
