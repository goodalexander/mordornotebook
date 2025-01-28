from setuptools import setup, find_packages

setup(
    name='mordornotebook',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'pandas',
        'sqlalchemy',
        'cryptography',
        'requests',
        'toml',
        'nest_asyncio',
        'brotli',
        'sec-cik-mapper',
        'psycopg2-binary',
        'quandl',
        'schedule',
        'openai',  # Required for OpenRouter
        'lxml',
        'aiohttp',  # For async operations with OpenRouter
        'asyncio',  # For async support
        'uuid',     # For generating unique identifiers
    ],
    author='Alex Good',
    author_email='goodalexander@gmail.com',
    description='Tool for Jupyter Notebooks to interact with codebases with AI',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/goodalexander/mordornotebook',  # Replace with your actual GitHub repo URL
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.11',
)