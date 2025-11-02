import os
from typing import List
from flask import current_app
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from commitary_backend.dto.gitServiceDTO import DiffDTO
from commitary_backend.dto.insightDTO import InsightItemDTO
from dotenv import load_dotenv
import logging

from langchain.callbacks import get_openai_callback


load_dotenv() # Loads env from .env

class RAGService:
    def __init__(self):
        CHATMODEL = os.getenv("OPENAI_DEFAULT_MODEL")
        self.llm = ChatOpenAI(model=CHATMODEL) # loads api key automatically from env

    def generate_insight_from_diff(self, repo_name: str, branch_name: str, diff_dto: DiffDTO, retrieved_docs: List[Document]) -> InsightItemDTO:
        """
        Generates a concise code insight from a DiffDTO, using retrieved documents as context.
        """
        current_app.logger.debug(f"Generating insight form diff")
        if not diff_dto.files:
            return InsightItemDTO(
                branch_name=branch_name,
                insight="No code changes were made on this branch for the given period."
            )

        # Combine all file patches into a single string
        MAX_PATCH_LENGTH_PER_FILE = 2000  # Adjust this value as needed

        diff_text = ""
        for file in diff_dto.files:
            patch_content = file.patch if file.patch else ""
            
            if len(patch_content) > MAX_PATCH_LENGTH_PER_FILE:
                patch_content = patch_content[:MAX_PATCH_LENGTH_PER_FILE] + "\n... (patch truncated)"

            diff_text += f"Filename: {file.filename}\nStatus: {file.status}\nPatch:\n{patch_content}\n\n"
                

            
            
            
        MAX_DIFF_LENGTH = 8000
        
        
        if len(diff_text) > MAX_DIFF_LENGTH:
            diff_text = diff_text[:MAX_DIFF_LENGTH] + "\n\n... (diff truncated)"
        # Format the retrieved documents for the prompt
        context_text = ""
        
        
        for doc in retrieved_docs:
            context_text += f"--- Context from {doc.metadata.get('filepath', 'unknown file')} ---\n"
            context_text += doc.page_content
            context_text += "\n\n"
            
        current_app.logger.debug(f"Final prompt component lengths before sending to OpenAI:")
        current_app.logger.debug(f"  - Context Text Length: {len(context_text)} characters")
        current_app.logger.debug(f"  - Diff Text Length:    {len(diff_text)} characters")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert software developer. Your task is to provide a professional analysis of the provided code changes."),

("user", """
Analyze the following code changes from the repository '{repo_name}' on branch '{branch_name}'.
Use the provided context to understand the scope and purpose of the modifications.

Present your analysis in the following structure, in Korean:

**1. 변경사항 요약 (Summary of Changes)**
* Provide a concise, high-level overview of the purpose and impact of these changes.

**2. 주요 변경 내역 (List of Key Changes)**
* Create a bulleted list of the specific modifications.
* Cite the relevant filenames, classes, or functions for import changes.
* Briefly explain what was changed.

**3. 기술적 분석 및 인사이트 (Technical Analysis and Insight)**
* Provide deeper insights into the changes. Consider architectural implications, potential risks, performance improvements, or adherence to coding best practices.

The entire response must be in formal, professional Korean. no emojis.

### Code Context (from the start of the week):
{context_text}

### Code Changes (today's diff):
{diff_text}
""")
        ])

        chain = prompt | self.llm
        # Corrected: Pass the actual values to the invoke method
        response = None 
        with get_openai_callback() as cb:
            response = chain.invoke({
            "repo_name": repo_name,
            "branch_name": branch_name,
            "context_text": context_text,
            "diff_text": diff_text
            })
            current_app.logger.debug(f"OpenAI Token Usage for Insight Generation : {cb}")

        return InsightItemDTO(
            branch_name=branch_name,
            insight=response.content
        )

# Singleton instance
rag_service = RAGService()