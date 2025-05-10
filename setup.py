from setuptools import setup, find_packages

setup(
    name="codeagent",
    version="0.1.0",
    description="An AI coding agent powered by Ollama",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "rich>=10.0.0",
        "pydantic>=2.0.0",
        "langchain>=0.1.0",
        "langchain-community>=0.0.10",
        "langchain-ollama>=0.0.1",
        "llama-index>=0.9.0",
        "chromadb>=0.4.18",
        "sentence-transformers>=2.2.0",
    ],
    entry_points={
        'console_scripts': [
            'codeagent=codeagent.main:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)