from graderchat.services.parselatex import parse_latex_soln
import os
import shutil
from pathlib import Path
import json
import os
import json
from openai import OpenAI

class Grader:
    def __init__(self, questions_root="questions", scratch_dir="scratch"):
        self.questions_root = questions_root
        self.scratch_dir = scratch_dir

        # Remove old scratch directory if it exists
        if os.path.exists(self.scratch_dir):
            shutil.rmtree(self.scratch_dir)

        # Recreate it fresh
        os.makedirs(self.scratch_dir, exist_ok=True)

        # Discover units
        self.units = self._discover_units() 

        # Create the OpenAI LLM client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise RuntimeError("Missing OPENAI_API_KEY environment variable")
        self.client = self.client = OpenAI(api_key=api_key)

    def _discover_units(self):
        units = {}

        # List everything inside the root directory
        for name in os.listdir(self.questions_root):
            folder = os.path.join(self.questions_root, name)

            print(f'Checking folder: {folder}')

            # Only consider subdirectories
            if not os.path.isdir(folder):
                continue

            # Find .tex and .json files inside this folder
            tex_files = [
                f for f in os.listdir(folder)
                if f.endswith(".tex")
            ]
            json_files = [
                f for f in os.listdir(folder)
                if f.endswith(".json")
            ]

            # Require exactly one of each
            if len(tex_files) != 1 or len(json_files) != 1:
                continue

            tex_path = os.path.join(folder, tex_files[0])
            json_path = os.path.join(folder, json_files[0])

            # Load JSON (plain‑text questions)
            with open(json_path, "r", encoding="utf-8") as f:
                questions_text = json.load(f)

            # Load LaTeX (original source)
            with open(tex_path, "r", encoding="utf-8") as f:
                latex_text = f.read()

            # Parse the latex solution 
            parsed_items = parse_latex_soln(latex_text)
            questions_latex = []
            ref_soln = []
            grading = []
            for item in parsed_items:
                questions_latex.append(item["question"])
                ref_soln.append(item["solution"])
                grading.append(item["grading"])

            

            # Check if questions_text length matches parsed items
            if len(questions_text) != len(parsed_items):
                err_msg = f"Warning: In unit '{name}', number of questions in JSON ({len(questions_text)})"\
                    + f" does not match number of parsed items in LaTeX ({len(parsed_items)})."
                print(err_msg)
                continue

            # Save unit info
            units[name] = {
                "folder": folder,
                "tex_path": tex_path,
                "json_path": json_path,
                "latex": latex_text,
                "questions_text": questions_text,
                "questions_latex": questions_latex,
                "solutions": ref_soln,
                "grading": grading,
            }
        if len(units) == 0:
            raise ValueError("No valid directories units found in '%s'." % self.questions_root)
        return units

    def grade(self, question_latex, ref_solution, grading_notes, student_soln):
        # ---------------------------------------------------------
        # 1. Build the task prompt
        # ---------------------------------------------------------
        task = f"""
            Your task is to grade a student's solution to an engineering problem.

            You must always return a single JSON object with the fields:
            - "result": "pass", "fail", or "error"
            - "full_explanation": a detailed explanation
            - "summary": a concise 2–3 sentence summary

            Follow these steps exactly:

            1. Determine whether the student solution appears to be for a *different* problem.
            - If misaligned:
                Return:
                {{
                    "result": "error",
                    "full_explanation": "There appears to be an alignment error. <explanation>",
                    "summary": "There is an alignment error between the question and the student solution."
                }}
            Do not attempt further grading.

            2. If aligned:
            - Compare the student solution to the reference solution.
            - Use the grading notes as guidance.
            - Provide a detailed step-by-step reasoning in "full_explanation".
            - Provide a concise 2–3 sentence summary in "summary".

            3. If correct:
                {{
                    "result": "pass",
                    "full_explanation": "<explanation>",
                    "summary": "The solution is correct. All required reasoning steps match the reference."
                }}

            4. If incorrect:
                {{
                    "result": "fail",
                    "full_explanation": "<explanation of what is correct and what is wrong>",
                    "summary": "The solution contains errors. The main issues are summarized concisely here."
                }}

            -------------------------
            QUESTION (LaTeX):
            {question_latex}

            REFERENCE SOLUTION:
            {ref_solution}

            GRADING NOTES:
            {grading_notes}

            STUDENT SOLUTION:
            {student_soln}
            """

        # ---------------------------------------------------------
        # 2. Write task prompt to scratch/task.txt
        # ---------------------------------------------------------
        task_path = os.path.join(self.scratch_dir, "task.txt")
        with open(task_path, "w") as f:
            f.write(task)

        # ---------------------------------------------------------
        # 3. Call OpenAI
        # ---------------------------------------------------------
        print('Calling OpenAI for grading...')
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[{"role": "user", "content": task}]
        )

        content = response.choices[0].message.content

        # ---------------------------------------------------------
        # 4. Save raw response to scratch/resp.json
        # ---------------------------------------------------------
        resp_path = os.path.join(self.scratch_dir, "resp.json")
        with open(resp_path, "w") as f:
            f.write(content)
        print(f'Grader response written to {resp_path}')

        # ---------------------------------------------------------
        # 5. Return parsed JSON to the caller
        # ---------------------------------------------------------
        try:
            return json.loads(content)
        except Exception:
            return {
                "result": "error",
                "full_explanation": "Model returned invalid JSON.",
                "summary": "The model output could not be parsed."
            }
    
    def load_solution_file(self, text):

        # Parse the latex solution file
        items = parse_latex_soln(text)

        quest_list = [item.get("question", "") for item in items]
        soln_list = [item.get("solution", "") for item in items]
        grading_notes_list = [item.get("grading", "") for item in items]
        resp = {
            "num_questions": len(items),
            "questions": quest_list,
            "solutions": soln_list,
            "grading_notes": grading_notes_list
        }
        print("Loaded solution file with %d items." % len(items))
    
    
        # You don’t need to return anything yet
        return resp
