#open_router_key = OpenRouterTool(openrouter_key=OPENROUTER_KEY)
from mordornotebook.wrangling.repo_export import *
from mordornotebook.settings.global_vars import OPENROUTER_KEY, REPO_PATHS
from openai import OpenAI
from pathlib import Path
import re
import json
import os
from IPython.display import display, Javascript
from agti.ai.openai import OpenAIRequestTool
from IPython.core.getipython import get_ipython
from IPython import get_ipython
import pandas as pd
from agti.ai.anthropic import AnthropicTool
from openai import OpenAI
class UserQuery:
    def __init__(self,notebook_name):
        self.tank_model= 'google/gemini-pro-1.5'
        self.mage_model = 'openai/o1'#'deepseek/deepseek-r1'
        self.query_context_history = {}
        self.notebook_name = f'{notebook_name}.ipynb'

    def get_notebook_contents(self):
        notebook_name = self.notebook_name
        def get_notebook_path(notebook_name):
            """Get the full path of the current Jupyter notebook."""
            try:
                # Get the current working directory
                current_dir = os.getcwd()
                # Combine with the provided notebook name
                return os.path.join(current_dir, notebook_name)
            except Exception as e:
                return f"Error determining path: {str(e)}"
        current_notebook_path = get_notebook_path(notebook_name)
        print(current_notebook_path)

        with open(current_notebook_path, "r", encoding="utf-8") as f:
            notebook_contents = json.load(f)
        return notebook_contents
    def convert_notebook_to_pretty_string(self):
        x=self.get_notebook_contents()
        raw_notebook = pd.DataFrame(x['cells'])[['source','outputs']].copy()
        def try_join(arr=[]):
            ret =''
            try:
                ret =''.join(arr)
            except:
                pass
            return ret
        raw_notebook['source_string']=raw_notebook['source'].apply(lambda x:try_join(x))
        raw_notebook['output_string']=raw_notebook['outputs'].apply(lambda x: str(x))
        str_creator = raw_notebook[['source_string','output_string']].copy()
        full_con_string = ''
        for cell in list(str_creator.index):
            
            cell_constructor = str(cell)+"""
"""
            input_constructor = str_creator.loc[cell]['source_string']+"""
    
OUTPUT:
"""
            output_constructor = str_creator.loc[cell]['output_string']+"""
__________________________
"""
            full_constructor = cell_constructor+input_constructor+output_constructor 
            full_con_string = full_con_string+full_constructor
            #raw_notebook['output_string']=raw_notebook['outputs'].apply(lambda x:''.join(x))
        return full_con_string
    
    def load_files_for_query(self, task_string='I want to spawn a data connection manager load a database and then read the most recent coinmarketcap data'):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_KEY,
        )
        
        output_string = export_multiple_repositories(REPO_PATHS)
        completion = client.chat.completions.create(
            extra_headers={
            },
            model=self.tank_model,##"deepseek/deepseek-r1",#"google/gemini-pro-1.5",
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": f"""Given this code base <CODE BASE STARTS HERE> {output_string}<CODE BASE ENDS HERE> 
                    give me the files required or highly relevant to completing the task {task_string}. Assume we have 
                    the parent github directory and start with the repository name.
                    1. Do not reference setup files. 
                    2. Do be thorough - if there are multiple files that fit the bill, include them.
                    3. Do not be too broad and choose tangential files that are unlikely related to the task performance
                    4. Understand that the scripts you pass will be referenced in the next step 
                    Provide your answer as a list of file strings such as the following:
                    ['agti/agtisecurity/example_script.py','narg/batchjobs/example_script2.py']"""
                }
            ]
        )
        all_strings = completion.choices[0].message.content
        def extract_filepaths(input_string):
            """
            Extract file paths listed within square brackets from the input string.
            
            Args:
                input_string (str): Input string containing file paths within square brackets
                
            Returns:
                list: List of extracted file paths
            """
            # Pattern to match content within square brackets
            pattern = r"\[(.*?)\]"
            
            # Find the match within square brackets
            bracket_match = re.search(pattern, input_string, re.DOTALL)
            
            if bracket_match:
                # Extract the content within brackets
                bracket_content = bracket_match.group(1)
                
                # Split the content by commas and clean up each path
                filepaths = [
                    path.strip().strip("'").strip('"')
                    for path in bracket_content.split(',')
                    if path.strip()
                ]
                
                return filepaths
            
            return []
        files_to_work = extract_filepaths(all_strings)
        
        
        def find_matching_files(repo_dirs, target_files):
            """
            Find full file paths by matching target files against repository directories.
            
            Args:
                repo_dirs (list): List of repository root directory paths
                target_files (list): List of relative file paths to find
                
            Returns:
                dict: Mapping of relative paths to their full file paths
            """
            # Convert repo directories to Path objects
            repo_paths = [Path(repo) for repo in repo_dirs]
            matched_files = {}
            
            for target in target_files:
                target_path = Path(target)
                
                # Check each repository directory
                for repo in repo_paths:
                    full_path = repo / target_path
                    if full_path.exists():
                        matched_files[target] = str(full_path.resolve())
                        break
            
            return matched_files
        all_files_to_load = list(find_matching_files(repo_dirs=REPO_PATHS, target_files=files_to_work).values())
        print(f'found repos to reference {all_files_to_load}')
        self.query_context_history[task_string] =all_files_to_load

    def output_code_context_block_for_task_string(self,task_string = 'I want to spawn a data connection manager load a database and then read the most recent coinmarketcap data'):        
        try:
            print('query not loaded, loading file context')
            self.query_context_history[task_string]
        except:
            self.load_files_for_query(task_string=task_string)
            pass
        files_to_load= self.query_context_history[task_string]
        print(f'The files referenced are {files_to_load}')
        
        def read_files_with_headers(file_paths):
            """
            Read multiple files and format their contents with clear header separators.
            
            Args:
                file_paths (list): List of file paths to read
                
            Returns:
                str: Formatted string containing all file contents with headers
            """
            formatted_output = []
            separator = "=" * 91  # 91 equals signs for consistent header formatting
            
            for file_path in file_paths:
                try:
                    path = Path(file_path)
                    content = path.read_text(encoding='utf-8')
                    
                    # Create the formatted header block
                    formatted_output.extend([
                        separator,
                        str(path),
                        separator,
                        content,
                        "\n"  # Add extra newline between files
                    ])
                except Exception as e:
                    formatted_output.extend([
                        separator,
                        f"Error reading {file_path}: {str(e)}",
                        separator,
                        "\n"
                    ])
            
            return "\n".join(formatted_output)
        
        # Example usage
        formatted_content = read_files_with_headers(files_to_load)
        return formatted_content

    def output_goal_and_task_response(self,original_goal,follow_on_task):
        """ 
        original_goal = 'I want to spawn a data connection manager load a database and then read the most recent coinmarketcap data'
        follow_on_task = "load the database connection then read the historical coinmarketcap pro market data  "
        """
        original_code_context =self.output_code_context_block_for_task_string(original_goal)
        notebook_content = self.convert_notebook_to_pretty_string()[0:200_000]
        system_prompt= """ You are the world's premier python coding expert designed to work inside of ipython Notebooks. 
        You are given a full Notebook Input log. 
        
        Here are some rules for your engagement
        1. When you output things it is code that can be directly pasted into an ipython notebook. That means if you provide comments you
        have to put ## in front of them to explain your work. 
        2. The code you should return should always work and you should be terse and provide minimal explanation outside
        of what is neccesary for the user to understand your 
        3. You do not need to preface your code with '''python - just output it with the assumption the user will add it into 
        a new cell in the notebook or print it out. You similarly do not need to end it with stuff like ```
        4. When you write code ensure that it is properly formatted and
        a. Conforms with the users existing coding style where possible
        b. Includes doc strings that include example usage in each function but are not overly verbose
        c. Are linted properly and would pass an interview at a top engineering firm for quality
        YOU ONLY OUTPUT STRINGS THAT CAN BE RUN IN IPYTHON NOTEBOOKS WITHOUT EDITS OR DELETIONS 
        """
        
        user_prompt=f"""
        Ingest the following context
        
        The original question is the context for why the user is asking the follow on question 
        <THE GOAL THE USER KICKED THIS JOB OFF WITH STARTS HERE>
        {original_goal}
        <THE GOAL THE USER KICKED THIS JOB OFF WITH ENDS HERE>
        
        The follow on task is what you need specifically to do as the next action in the workflow 
        <THE FOLLOW ON TASK STARTS HERE>
        {follow_on_task}
        <THE FOLLOW ON TASK ENDS HERE>
        
        <THE RELEVANT CODE REFERENCE FOR THE ORIGINAL GOAL STARTS HERE>
        {original_code_context}
        <THE RELEVANT CODE REFERENCE FOR THE ORIGINAL GOAL ENDS HERE>
        
        <FULL IPYTHON NOTEBOOK CONTENT STARTS HERE>
        {notebook_content}
        <FULL IPYTHON NOTEBOOK CONTENT ENDS HERE>
        
        
        Here are some guidelines
        1. The user has outlined an original goal which outlines the scope of what is trying to be accomplished overall
        2. The system has pulled down relevant code for the original goal which you can reference (RELEVANT CODE REFERENCE)
        3. The system has outputted full ipython notebook content which includes the current state and workflows of the user
        trying to implement this goal 
        4. The thing which you need to respond to and action specifically is the FOLLOW ON TASK. Your primary 
        deliverable will be a piece of code potentially with some explanations. It will be in an ipython notebook.
        If what you output is not runnable in an ipython notebook you will be fired. If you have explanations format them
        like 
        # explanation for code 
        or put the relevant explanation in the function doc strings.
        5. The code you generate will be pasted into the next cell of the Ipython Notebook so make sure that your output can be pasted into a cell
        per the examples above
        6. It is best if you keep your commentary terse and include the relevant information in your doc strings 
        The user doesn't need explanations he needs results. Make sure to get the code right and without errors.
        7. The user might refer to errors in the notebook - which will be denoted in output cells 
        8. Try and conform with the user's code style as much as possible while being professional
        9. Output high grade professional code 
        
        For your output ONLY RETURN WHAT IS DENOTED AS THE FOLLOW ON TASK with reference to the original goal.
        YOUR JOB IS TO OUTPUT CODE AND EXPLANATIONS NOT OTHER TEXT. DO NOT STRAY FROM THE ASSIGMENT 
        
        Now: given these params help the user with this: {follow_on_task}
        """
        
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_KEY,
        )
        
        completion2 = client.chat.completions.create(
            extra_headers={},
            model=self.mage_model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        code= completion2.choices[0].message.content
        code = code.replace('```python','').replace('```','')
        shell = get_ipython()
        shell.set_next_input(code, replace=False)