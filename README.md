# Upstage Document Parser (Streamlit Single App)

This project runs as a single Streamlit app and calls the Upstage Document API directly.

## Run

```bash
pip install -r requirements.txt
streamlit run frontend/app.py
```

Open http://localhost:8501.

## API Key

- Add keys in the sidebar.
- Keys are stored locally at `storage/api_keys.json`.
- Select which key to use from the dropdown.

## Storage

Uploaded files and parsed results are stored under `storage/`.
