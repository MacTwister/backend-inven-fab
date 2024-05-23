
# API for Retrieving Google Sheets Inventory Data for Fab24

This API establishes a connection with Google Sheets to extract data from a designated spreadsheet. In the development environment, Flask serves as the backend framework. For the production environment, the application has been deployed on Render (https://render.com). The WebService is accessible at the following URL: https://backend-inven-fab24.onrender.com.

## Environment Setup

Before running the API, ensure you have the following tools and files:

- Python 3.x
- pip (Python package manager)
- `credentials.json` file from Google Cloud Platform with OAuth 2.0 credentials
- `.env` file with necessary environment variables

## Installation

Clone the repository and navigate to its directory:

```bash
$ git clone https://github.com/Mozta/backend_inven_fab24.git
$ cd backend_inven_fab24
```

Install dependencies:

```bash
$ pip install -r requirements.txt
```

## Environment Variables Configuration

Create a `.env` file in the root directory of the project with the following variables:

```
SCOPES=[Your Google Sheets scopes]
SPREADSHEET_ID=[Your Google Sheets spreadsheet ID]
RANGE_NAME=[Cell range to access]
BASE_URL=[Base path for your endpoints]
```

## Execution

Start the application with Flask:

```bash
$ python app.py
```

## Endpoints

### GET /{BASE_URL}

Returns spreadsheet data as JSON.

### GET /{BASE_URL}/items

Retrieves values from the 'Items' column of the spreadsheet.

## Google Authentication

The API uses the OAuth 2.0 flow to authenticate with the Google Sheets API. On first run, you'll be prompted to log in with your Google account to grant the necessary permissions.

## Error Handling

The API returns an error message in JSON format if no data is found in the spreadsheet.

## Production

