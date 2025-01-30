# mordornotebook
Terrible hack for millennials who still use Jupyter notebook but want to use AI. I also dislike Cursor bc it's too presumptuous and Claude is a weaker model than o1 in terms of getting code right in 1 shot 

The way Mordor Notebook works is it ingests your whole repositories, processes them via a huge context model such as Gemini Pro (the tank) -- into a list of relevant scripts related to "The Goal".
These scripts get cached. Then -- they're referenced along with the notebook content for completing tasks. 

You need to register for an API key for Mordor Notebook to work 
OpenRouter's website is here: https://openrouter.ai

To use Mordor Notebok you'll need OpenRouter and a Level 5 OpenAI API key loaded into your OpenRouter API. If you don't have the level 5 OpenAI key then I recommend swapping out o1
with deepseek r1 

Line 119 of wrangling/jupyer_tool.py 
Change self.mage_model = 'openai/o1'#'deepseek/deepseek-r1'
to
self.mage_model = 'deepseek/deepseek-r1'

For your tank you want a 1m+ context model, and for your mage you want a strong reasoning model. I'll do my best to update this over time with the best model

## Suggested usage

Download repository then ~/repos/mordornotebook$ pip install -e .

from mordornotebook.settings.global_vars import *
from mordornotebook.wrangling.jupyter_tool import UserQuery

Once you do this you'll get a toolbar 

(if you've already installed you'll see something like this)
____
Existing configuration found:
GitHub directory: C:/Users/goodalexander/OneDrive/Documents/GitHub
Referenced repositories:
- agti
- narg

Would you like to keep the existing configuration (1) or re-enter (0)?
____
if you enter re-enter (0)

you'll be prompted to enter your Github repository path 
Please enter your GitHub directory path:
C:/Users/goodalexander/OneDrive/Documents/GitHub (in my case)

This should be where you have your Github Repositories saved 

After you do this you'll be prompted for the repositories you want to include in the Mordor Notebook helper

Available repositories:
1. agti
2. goodalexander.github.io
3. goodalexanderinfra
4. mordornotebook
5. narg
6. pftpyclient
7. sanjuancapital
8. secondfoundation
9. shipyardtech
10. trading

In my case I just want agti,narg so I enter that in the input box 

Then I get

Selected repositories saved:
- agti
- narg

Found existing OpenRouterKey

Let's say you're in a notebook called DE_demo -- this is how you use the helper

user_query = UserQuery(notebook_name='DE_demo')
user_query.output_goal_and_task_response(original_goal='could you please output a function that outputs the most recent coinmarketcap pro data',
                                         follow_on_task='I want the data that is updated with live data -- should be a function inside cmcpro pull')

original_goals will be cached in the class. Each time they are run they'll use the "tank model" i.e. Gemini Pro to load in the relevant scripts from the repos you choose

When you're working on a new goal change the original goal string. This takes longer but will refresh the context. 

