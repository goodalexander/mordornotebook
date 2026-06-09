from setuptools import setup, find_packages

# Read requirements from requirements.txt if you have one
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='mordornotebook',
    version='0.2.0',
    packages=find_packages(include=['mordornotebook', 'mordornotebook.*']),
    package_data={
        'mordornotebook': [
            'labextension/package.json',
            'labextension/static/*',
            'labextension/schemas/*',
            'labextension/themes/*',
            'jupyter-config/jupyter_server_config.d/mordornotebook.json',
        ],
    },
    install_requires=[],
    extras_require={
        'notebook': ['ipython', 'jupyter_server', 'jupyterlab', 'nbformat'],
        'pandas': ['pandas'],
        'legacy': ['openai', 'pandas', 'nest_asyncio'],
        'test': ['pytest', 'pandas'],
    },
    entry_points={
        'console_scripts': [
            'mordorctl=mordornotebook.cli:main',
        ],
    },
    data_files=[
        (
            'etc/jupyter/jupyter_server_config.d',
            ['mordornotebook/jupyter-config/jupyter_server_config.d/mordornotebook.json'],
        ),
    ],
    author='Alex Good',
    author_email='goodalexander@users.noreply.github.com',
    description='Codex-native JupyterLab workflow with tmux audit trail and notebook memory bridge',
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
