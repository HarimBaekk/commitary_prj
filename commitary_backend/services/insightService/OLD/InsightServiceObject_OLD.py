import os
from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import psycopg2
import tiktoken
from commitary_backend.services.githubService.GithubServiceObject import gb_service
from commitary_backend.services.insightService.OLD.RAGService_OLD import rag_service as rag_service_old
from commitary_backend.dto.insightDTO import DailyInsightDTO, DailyInsightListDTO, InsightItemDTO
from commitary_backend.dto.gitServiceDTO import CodebaseDTO, CodeFileDTO, CommitListDTO, DiffDTO, RepoDTO

from datetime import date, datetime, timedelta, timezone

from langchain.callbacks import get_openai_callback
from flask import current_app
import logging


from commitary_backend.commitaryUtils.dbConnectionDecorator import with_db_connection



import os
from typing import List, Optional, Dict, Any
import torch
from transformers import AutoTokenizer, AutoModel
from langchain_core.embeddings import Embeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.documents import Document



'''
CREATE TABLE IF NOT EXISTS "daily_insight" (
    daily_insight_id SERIAL PRIMARY KEY,
    date DATE,
    commitary_id INT,
    repo_name TEXT,
    repo_id INT,
    activity BOOLEAN,
    CONSTRAINT fk_commitary_id
        FOREIGN KEY (commitary_id)
        REFERENCES "user_info"(commitary_id)
);

CREATE TABLE IF NOT EXISTS "insight_item" (
    insight_item_id SERIAL PRIMARY KEY,
    repo_name TEXT,
    repo_id INT,
    branch_name TEXT,
    insight TEXT,
    daily_insight_id INT,
    CONSTRAINT fk_daily_insight
        FOREIGN KEY (daily_insight_id)
        REFERENCES "daily_insight"(daily_insight_id)
);
'''

from dotenv import load_dotenv
load_dotenv()


class LoggingOpenAIEmbeddings(OpenAIEmbeddings):
    """
    A custom OpenAIEmbeddings class that logs the number of tokens used.
    """
    def _get_token_count(self, texts: List[str]) -> int:
        """Helper function to count tokens using tiktoken."""
        # Note: The model name might need to be adjusted based on the specific
        # embedding model you're using (e.g., "text-embedding-ada-002").
        # "cl100k_base" is the encoding for text-embedding-ada-002.
        encoding = tiktoken.get_encoding("cl100k_base")
        
        total_tokens = 0
        for text in texts:
            total_tokens += len(encoding.encode(text))
        return total_tokens

    def embed_documents(self, texts: List[str], chunk_size: Optional[int] = 0) -> List[List[float]]:
        """Override embed_documents to add logging."""
        token_count = self._get_token_count(texts)
        current_app.logger.debug(f"Embedding {len(texts)} documents. Token count (estimated): {token_count}")
        return super().embed_documents(texts, chunk_size)

    def embed_query(self, text: str) -> List[float]:
        """Override embed_query to add logging."""
        token_count = self._get_token_count([text])
        current_app.logger.debug(f"Embedding a single query. Token count (estimated): {token_count}")
        return super().embed_query(text)

class InsightService():
    
    def __init__(self):
        self.embeddings = LoggingOpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            length_function=len
        )
        # Assuming DATABASE_URL is in the environment for PGVector
        self.connection_string = os.getenv("DATABASE_URL")
        self.vector_store = PGVector(
    connection=self.connection_string,
    embeddings=self.embeddings,
    collection_name="codebase_snapshots_OLD"
)
    def _embed_and_store_codebase(self, codebase_dto: CodebaseDTO, commitary_id: int, branch: str, repo_id: int,snapshot_week_id:str):
        """
        Chunks, embeds, and stores the codebase snapshot in the vector database.
        """
        current_app.logger.debug(f"embed_and_store_codebase")
        documents = []
        for file in codebase_dto.files:
            chunks = self.text_splitter.split_text(file.code_content)
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "commitary_user": commitary_id,
                        "repo_name": codebase_dto.repository_name,
                        "repo_id": repo_id,
                        "target_branch": branch,
                        "filepath": file.path,
                        "type": "codebase",
                        "lastModifiedTime": file.last_modified_at.isoformat(),
                        "snapshot_week_id": snapshot_week_id,
                        "chunk_id": f"{repo_id}_{branch}_{file.path}_{i}",
                        "collection_name": "OLD"
                    }
                )
                documents.append(doc)
        
        if documents:
            current_app.logger.debug(f"Attempting to embed and store {len(documents)} document chunks for codebase snapshot.")
            
            # Process documents in batches to avoid timeouts and memory issues.
            batch_size = 16
            with get_openai_callback() as cb:
                for i in range(0, len(documents), batch_size):
                    batch = documents[i:i + batch_size]
                    self.vector_store.add_documents(batch)
                    current_app.logger.debug(f"  - Successfully processed batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}")
                current_app.logger.debug(f"OpenAI Token Usage for Embedding: {cb}")

            current_app.logger.debug(f"Successfully embedded and stored all document chunks.")
        else:
            current_app.logger.debug("No documents to embed for this codebase snapshot.")
            
    
    @with_db_connection
    def createDailyInsight(self,  commitary_id: int, repo_id: int, start_datetime: datetime, branch: str, user_token: str,conn=None) -> int:
        """
        Creates a daily insight for a specific branch using a RAG system. It fetches a snapshot from the previous Monday,
        embeds it if it doesn't exist, and then uses it as context to analyze the diff for the given day.
        """
        current_app.logger.debug(f"{datetime.now()} debug code")

        try:
            insight_date = start_datetime.date()
            
            
            current_app.logger.debug(f"DEBUG: Processing insight for date: {insight_date}, repo_id: {repo_id}, branch: {branch}")
            
            # Step 0: Check if an insight for this specific branch and date already exists.
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM insight_item ii
                    JOIN daily_insight di ON ii.daily_insight_id = di.daily_insight_id
                    WHERE di.commitary_id = %s
                    AND di.repo_id = %s
                    AND di.date = %s
                    AND ii.branch_name = %s
                """, (commitary_id, repo_id, insight_date, branch))
                if cur.fetchone():
                    current_app.logger.debug("DEBUG: Insight for this branch and date already exists.")
                    return 1 # Status: Already exists

            # Step 1: Get the most recent Monday
            today = insight_date
            monday_date = today - timedelta(days=today.weekday())
            monday_start_datetime = datetime.combine(monday_date, datetime.min.time(), tzinfo=timezone.utc)
            snapshot_week_id_str = monday_date.isoformat()  # e.g., "2025-09-15"

            # Step 1.5: Check if the snapshot for this Monday already exists using the new ID
            snapshot_exists = False
            with conn.cursor() as cur:
                # THIS IS THE CORRECTED QUERY for your schema
                cur.execute(
                    """
                    SELECT 1 FROM langchain_pg_embedding
                    WHERE cmetadata->>'repo_id' = %s
                    AND cmetadata->>'target_branch' = %s
                    AND cmetadata->>'snapshot_week_id' = %s
                    AND cmetadata->>'type' = 'codebase'
                    AND cmetadata->>'collection_name' = 'OLD'
                    LIMIT 1
                    """,
                    (str(repo_id), branch, snapshot_week_id_str) # Cast repo_id to string for JSONB query
                )
                if cur.fetchone():
                    snapshot_exists = True
                    print(f"DEBUG: Codebase snapshot for week of {snapshot_week_id_str} already exists.")

            repo_dto: RepoDTO = gb_service.getSingleRepoByID(user_token, repo_id)
            if not repo_dto:
                print("ERROR: Repository not found on GitHub.")
                return 2

            if not snapshot_exists:
                print(f"DEBUG: Fetching codebase snapshot for Monday: {monday_start_datetime}")
                monday_snapshot: Optional[CodebaseDTO] = gb_service.getSnapshotByIdDatetime(user_token, repo_id, branch, monday_start_datetime)

                if monday_snapshot and monday_snapshot.files:
                    # Pass the new stable ID when storing the snapshot
                    self._embed_and_store_codebase(monday_snapshot, commitary_id, branch, repo_id, snapshot_week_id_str)
                else:
                    print("DEBUG: No codebase snapshot found for Monday. Proceeding without RAG context.")



            # Step 3: Get the diff from the start of the week to the target date
            end_of_day = datetime.combine(insight_date, datetime.max.time(), tzinfo=timezone.utc)
            diff_dto: DiffDTO = gb_service.getDiffByIdTime3(
                user_token=user_token, repo_id=repo_id,
                branch=branch,
                datetime_from=monday_start_datetime, datetime_to=end_of_day
            )
            current_app.logger.debug(f"DEBUG: diff_dto retrieved.")
            # Step 4: Handle no diff
            if not diff_dto or not diff_dto.files:
                current_app.logger.debug("DEBUG: No activity found for the specified date.")
                activity_status = False
                
                with conn.cursor() as cur:
                    # Find or create daily_insight and set its activity to false if it doesn't exist
                    cur.execute(
                        "SELECT daily_insight_id FROM daily_insight WHERE commitary_id = %s AND repo_id = %s AND date = %s",
                        (commitary_id, repo_id, insight_date)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO daily_insight (date, commitary_id, repo_name, repo_id, activity) VALUES (%s, %s, %s, %s, %s)",
                            (insight_date, commitary_id, repo_dto.github_name, repo_id, activity_status)
                        )
                    conn.commit()
                return -1 # Status: No activity
            
            activity_status = True
            retrieved_docs = None
            # Step 5: Retrieve relevant documents from the vector store
            
            diff_content_for_retrieval = " ".join([f.patch for f in diff_dto.files if f.patch])            
            MAX_RETRIEVAL_QUERY_LENGTH = 100000  # Set a safe character limit for the query
            if len(diff_content_for_retrieval) > MAX_RETRIEVAL_QUERY_LENGTH:
                diff_content_for_retrieval = diff_content_for_retrieval[:MAX_RETRIEVAL_QUERY_LENGTH]
 

            retriever = self.vector_store.as_retriever(search_kwargs={'k': 3,
                                                                              'filter': {
            "$and": [
                {"commitary_user": commitary_id},
                {"repo_id": repo_id}
            ]
        }})
            
            try:
                current_app.logger.debug("Attempting to retrieve documents from vector store...")
                current_app.logger.debug(f"  - Size of content for retrieval: {len(diff_content_for_retrieval)} characters")
                
                # ADD THIS with BLOCK and the log line
                with get_openai_callback() as cb:
                    retrieved_docs = retriever.invoke(diff_content_for_retrieval)
                    current_app.logger.debug(f"OpenAI Token Usage for Retrieval Query Embedding: {cb}")


                current_app.logger.debug(f"Successfully retrieved {len(retrieved_docs)} documents from vector store.")

            except Exception as e:
                current_app.logger.error("CRITICAL: Failed during vector store retrieval (retriever.invoke). This is the point of failure.", exc_info=True)
                # Re-raise the exception or return an error status
                # For now, let's return the error status to stop the process gracefully
                return 2 # Status: Error
            current_app.logger.debug(f"DEBUG: Retrieved {len(retrieved_docs)} documents for context.")

            # Step 6: Generate insight with RAG context
            insight_item: InsightItemDTO = rag_service_old.generate_insight_from_diff(
                repo_dto.github_name, branch, diff_dto, retrieved_docs
            )
            # Step 7: Save the insight into the database
            with conn.cursor() as cur:
                # Find or create the daily_insight entry for the day
                cur.execute(
                    "SELECT daily_insight_id FROM daily_insight WHERE commitary_id = %s AND repo_id = %s AND date = %s",
                    (commitary_id, repo_id, insight_date)
                )
                result = cur.fetchone()
                if result:
                    daily_insight_id = result[0]
                    # If activity is true, make sure to update the daily_insight record
                    cur.execute(
                        "UPDATE daily_insight SET activity = TRUE WHERE daily_insight_id = %s",
                        (daily_insight_id,)
                    )
                else:
                    cur.execute(
                        "INSERT INTO daily_insight (date, commitary_id, repo_name, repo_id, activity) VALUES (%s, %s, %s, %s, %s) RETURNING daily_insight_id",
                        (insight_date, commitary_id, repo_dto.github_name, repo_id, activity_status)
                    )
                    daily_insight_id = cur.fetchone()[0]


                # Insert into insight_item table
                cur.execute(
                    "INSERT INTO insight_item (repo_name, repo_id, branch_name, insight, daily_insight_id) VALUES (%s, %s, %s, %s, %s)",
                    (repo_dto.github_name, repo_id, branch, insight_item.insight, daily_insight_id)
                )

                conn.commit()
            
            current_app.logger.debug("DEBUG: Insight successfully created and saved.")
            return 0 # Status: Success

        except Exception as e:
            conn.rollback()
            current_app.logger.debug(f"ERROR: An exception occurred while creating insight: {e}")
            return 2 # Status: Error
        
    @with_db_connection
    def getInsights(self,commitary_id: int, repo_id: int, start_datetime: datetime, end_datetime: datetime,conn=None) -> DailyInsightListDTO:
        """
        Retrieves daily insights for a given user and repository within a specified date range.
        """
        try:
            start_date = start_datetime.date()
            end_date = end_datetime.date()

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        di.daily_insight_id,
                        di.date,
                        di.commitary_id,
                        di.repo_name,
                        di.repo_id,
                        di.activity,
                        ii.branch_name,
                        ii.insight
                    FROM daily_insight di
                    LEFT JOIN insight_item ii ON di.daily_insight_id = ii.daily_insight_id
                    WHERE
                        di.commitary_id = %s AND
                        di.repo_id = %s AND
                        di.date >= %s AND
                        di.date <= %s
                    ORDER BY di.date DESC, ii.insight_item_id;
                    """,
                    (commitary_id, repo_id, start_date, end_date)
                )
                rows = cur.fetchall()

            daily_insights_map = {}

            for row in rows:
                (daily_insight_id, date_of_insight, _, repo_name, _,
                 activity, branch_name, insight_text) = row

                if daily_insight_id not in daily_insights_map:
                    daily_insights_map[daily_insight_id] = DailyInsightDTO(
                        commitary_id=commitary_id,
                        repo_name=repo_name,
                        repo_id=repo_id,
                        date_of_insight=date_of_insight,
                        activity=activity,
                        items=[]
                    )

                if branch_name and insight_text:
                    daily_insights_map[daily_insight_id].items.append(
                        InsightItemDTO(branch_name=branch_name, insight=insight_text)
                    )
            
            # Return the list of insights wrapped in the new DTO
            return DailyInsightListDTO(insights=list(daily_insights_map.values()))

        except Exception as e:
            current_app.logger.debug(f"ERROR: An exception occurred while retrieving insights: {e}")
            return DailyInsightListDTO(insights=[])

# Singleton instance
insight_service = InsightService()