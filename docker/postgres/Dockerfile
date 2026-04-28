# PostgreSQL 18 with pgvector supplied by the vetted pgvector image.
# docker/postgres/init.sql fails fast if PG18, vector, or pg_trgm are unavailable.
ARG PGVECTOR_POSTGRES_IMAGE=pgvector/pgvector:pg18
FROM ${PGVECTOR_POSTGRES_IMAGE}

COPY init.sql /docker-entrypoint-initdb.d/00-pragma-extensions.sql
RUN chmod 0644 /docker-entrypoint-initdb.d/00-pragma-extensions.sql
