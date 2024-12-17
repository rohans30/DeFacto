# README for backend

1. Install the necessary dependencies for the API with the following command:
pip install -r requirements.txt

2. You need an OpenAPI Key to use our application locally. Create an account and create an api key. Then
save it to your system with the following command:

    export OPENAI_API_KEY={Your_Api_key}

3. Run the API with the following command:
uvicorn app:app --reload