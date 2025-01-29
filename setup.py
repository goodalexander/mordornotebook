from setuptools import setup, find_packages

# Read requirements from requirements.txt if you have one
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='mordornotebook',
    version='0.1.0',
    packages=find_packages(include=['mordornotebook', 'mordornotebook.*']),
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
        'openai',
        'lxml',
        'aiohttp',
        'asyncio',
    ],
    author='Alex Good',
    author_email='goodalexander@gmail.com',
    description='Tool for Jupyter Notebooks to interact with codebases with AI',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/goodalexander/mordornotebook',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.11',
    include_package_data=True,
)