import os
import json
import requests
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()

# IMPORTANT: Set this to the address of your running Flask server
# BASE_URL =   # Example: "http://your-remote-server.com"
BASE_URL = os.getenv("API_URL")
# Get the GitHub token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
print(f"Using GitHub Token: {'*' * 10}{GITHUB_TOKEN[-4:]}" if GITHUB_TOKEN else "Token not found!")


# Test constants
#TEST_REPO_ID = 1054736566
TEST_USER = "HarimBaekk"
TEST_REPO_NAME = "commitary_prj"  # ✅ 추가

# --- Helper Functions ---

def print_test_header(test_name):
    """Prints a formatted header for each test function."""
    print("\n" + "="*50)
    print(f"  RUNNING TEST: {test_name}")
    print("="*50)

def check_response(response, expected_status_code=200):
    """Checks the response and prints success or failure messages."""
    print("--- RAW RESPONSE TEXT ---")
    print(response.text)
    print("-------------------------")
    
    if response.status_code == expected_status_code:
        print(f"SUCCESS: Received expected status code {response.status_code}")
        return True
    else:
        print(f"FAILURE: Expected status code {expected_status_code}, but got {response.status_code}")
        return False

def get_json_safely(response):
    """Attempts to decode JSON and handles errors gracefully."""
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        print(f"FAILURE: Could not decode JSON. Error: {e}")
        print("The raw response text above was not valid JSON.")
        return None
    
# ✅ 추가: 레포지토리 ID 찾기 함수
def get_repo_id_by_name(username: str, repo_name: str, token: str) -> int:
    """레포지토리 이름으로 ID 찾기 (GitHub API 직접 호출)"""
    print(f"Searching for repository: {username}/{repo_name}")
    
    # GitHub API 직접 호출
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 특정 레포 정보 가져오기
    github_url = f"https://api.github.com/repos/{username}/{repo_name}"
    response = requests.get(github_url, headers=headers)
    
    if response.status_code == 200:
        repo_data = response.json()
        repo_id = repo_data['id']
        print(f"Found repo ID: {repo_id}")
        return repo_id
    else:
        print(f"ERROR: Repository {username}/{repo_name} not found")
        print(f"Status code: {response.status_code}")
        if response.status_code == 404:
            print("Possible reasons:")
            print("  - Repository doesn't exist")
            print("  - Repository is private and token doesn't have access")
            print("  - Username or repo name is incorrect")
        return None

# --- Test Functions ---

def test_get_user():
    print_test_header("test_get_user")
    params = {'token': GITHUB_TOKEN}
    response = requests.get(f"{BASE_URL}/user", params=params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response:")
            print(json.dumps(json_data, indent=2))

def test_get_repos():
    print_test_header("test_get_repos")
    params = {'user': TEST_USER, 'token': GITHUB_TOKEN}
    response = requests.get(f"{BASE_URL}/repos", params=params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response:")
            print(json.dumps(json_data, indent=2))

def test_get_branches():
    print_test_header("test_get_branches")
    params = {'token': GITHUB_TOKEN, 'repo_id': TEST_REPO_ID}
    response = requests.get(f"{BASE_URL}/branches", params=params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response:")
            print(json.dumps(json_data, indent=2))

def test_get_diff():
    print_test_header("test_get_diff")
    dt_from_str = "2025-08-21T10:00:00Z"
    dt_to_str = "2025-08-24T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'yh_1',
        'branch_to': 'yh_1',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str,
        'default_branch': 'main'
    }
    response = requests.get(f"{BASE_URL}/diff", params=query_params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response received.")
            filename = "diff_data.json"
            with open(filename, 'w') as json_file:
                json.dump(json_data, json_file, indent=4)
            print(f"Data successfully saved to {filename}")

def test_get_commits():
    print_test_header("test_get_commits")
    dt_from_str = "2025-07-20T10:00:00Z"
    dt_to_str = "2025-07-29T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_name': 'yh_9',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str
    }
    response = requests.get(f"{BASE_URL}/githubCommits", params=query_params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            # Define the output filename
            output_filename = "github_commits_response.json"
            
            # Open the file in write mode ('w') and save the data
            # encoding='utf-8' is best practice for handling text data
            with open(output_filename, 'w', encoding='utf-8') as f:
                # json.dump() writes the object to the file
                # indent=2 makes the JSON file human-readable
                json.dump(json_data, f, indent=2)
            
            print(f"Full JSON response successfully saved to {output_filename}")


def test_get_commits2():
    print_test_header("test_get_commits2") # Changed header for clarity
    dt_from_str = "2025-07-20T10:00:00Z"
    dt_to_str = "2025-07-29T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_name': 'yh_9',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str
    }
    response = requests.get(f"{BASE_URL}/githubCommits2", params=query_params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            # Define a different output filename
            output_filename = "github_commits_response2.json"

            # Open the file in write mode ('w') and save the data
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)

            print(f"Full JSON response successfully saved to {output_filename}")
            

def test_get_diff_invalid_datetime():
    print_test_header("test_get_diff_invalid_datetime")
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'main',
        'branch_to': 'feature-branch',
        'datetime_from': "not-a-valid-date",
        'datetime_to': "2023-10-27T10:00:00Z"
    }
    response = requests.get(f"{BASE_URL}/diff", params=query_params)
    # Expecting a 400 Bad Request, so we pass that to our checker
    check_response(response, expected_status_code=400)


def test_repo_lifecycle():
    print_test_header("test_repo_lifecycle")

    # 1. Get user info to retrieve commitary_id
    print("\n--- Step 1: Get User ---")
    user_response = requests.get(f"{BASE_URL}/user", params={'token': GITHUB_TOKEN})
    if not check_response(user_response): return
    user_json = get_json_safely(user_response)
    if not user_json: return
    commitary_id = user_json.get("commitary_id")
    print(f"Successfully retrieved commitary_id: {commitary_id}")

    # 2. Get repos and select one to register
    print("\n--- Step 2: Get Repos ---")
    repos_response = requests.get(f"{BASE_URL}/repos", params={'user': TEST_USER, 'token': GITHUB_TOKEN})
    if not check_response(repos_response): return
    repos_json = get_json_safely(repos_response)
    if not repos_json or not repos_json.get('repoList'):
        print("FAILURE: No repositories found.")
        return
    first_repo = repos_json['repoList'][0]
    repo_id_to_test = first_repo['github_id']
    print(f"Selecting repo with ID: {repo_id_to_test} to test.")

    # 3. Register the selected repository
    print("\n--- Step 3: Register Repo ---")
    register_params = {'token': GITHUB_TOKEN, 'repo_id': repo_id_to_test, 'commitary_id': commitary_id}
    register_response = requests.post(f"{BASE_URL}/registerRepo", params=register_params)
    # The status code could be 201 (Created) or 409 (Conflict), we check for either
    if register_response.status_code not in [201, 409]:
        check_response(register_response, expected_status_code=201) # This will show the error
        return
    print(f"Registration response status code: {register_response.status_code} (This is OK)")

    # 4. Get the registered repository
    print("\n--- Step 4: Get Registered Repos ---")
    get_registered_response = requests.get(f"{BASE_URL}/registeredRepos", params={'commitary_id': commitary_id})
    if not check_response(get_registered_response): return
    registered_repos_json = get_json_safely(get_registered_response)
    if not registered_repos_json: return
    
    if any(repo['github_id'] == repo_id_to_test for repo in registered_repos_json.get('repoList', [])):
        print("Successfully found the registered repo.")
    else:
        print("FAILURE: Did not find the newly registered repo.")
        return

    # 5. Delete the registered repository
    print("\n--- Step 5: Delete Repo ---")
    delete_params = {'repo_id': repo_id_to_test, 'commitary_id': commitary_id}
    delete_response = requests.delete(f"{BASE_URL}/deleteRepo", params=delete_params)
    if not check_response(delete_response): return
    print("Successfully deleted the registered repo.")

    # 6. Verify the deletion
    print("\n--- Step 6: Verify Deletion ---")
    get_after_delete_response = requests.get(f"{BASE_URL}/registeredRepos", params={'commitary_id': commitary_id})
    if not check_response(get_after_delete_response): return
    repos_after_delete_json = get_json_safely(get_after_delete_response)
    if not repos_after_delete_json: return

    if not any(repo['github_id'] == repo_id_to_test for repo in repos_after_delete_json.get('repoList', [])):
        print("Successfully verified the repo was deleted.")
    else:
        print("FAILURE: Repo was still found after deletion.")


def test_insight_lifecycle():
    print_test_header("test_insight_lifecycle")

    # 1. Get user info to retrieve commitary_id
    print("\n--- Step 1: Get User for Insight Test ---")
    user_response = requests.get(f"{BASE_URL}/user", params={'token': GITHUB_TOKEN})
    if not check_response(user_response): return
    user_json = get_json_safely(user_response)
    if not user_json: return
    commitary_id = user_json.get("commitary_id")
    print(f"Retrieved commitary_id: {commitary_id}")

    # 2. Create insights
    print("\n--- Step 2: Create Insights ---")
    dates_to_create = ["2025-09-14T12:00:00Z","2025-09-15T12:00:00Z", "2025-09-16T12:00:00Z"]
    for date_str in dates_to_create:
        create_params = {
            'token': GITHUB_TOKEN,
            'repo_id': TEST_REPO_ID,
            'commitary_id': commitary_id,
            'date_from': date_str,
            'branch': "yh_11"
        }
        create_response = requests.post(f"{BASE_URL}/createInsight", params=create_params)
        if create_response.status_code not in [201, 409, 200]:
            check_response(create_response, 201) # Show error if not an expected code
            return
        print(f"Create insight for {date_str} - Status: {create_response.status_code} (This is OK)")

    # 3. Retrieve insights
    print("\n--- Step 3: Retrieve Insights ---")
    start_date = "2025-09-11T00:00:00Z"
    end_date = "2025-09-17T23:59:59Z" 
    get_params = {
        'repo_id': TEST_REPO_ID,
        'commitary_id': commitary_id,
        'date_from': start_date,
        'date_to': end_date
    }
    get_response = requests.get(f"{BASE_URL}/insights", params=get_params)
    if check_response(get_response):
        json_data = get_json_safely(get_response)
        if json_data:
            print("Successfully retrieved insights.")
            print("Insights data:")
            print(json.dumps(json_data, indent=2))

def test_other_user_repository():
    """다른 사용자의 레포지토리로 테스트"""
    print_test_header("test_other_user_repository")
    
    # 옵션 1: OAuth 로그인 (해당 사용자의 토큰 필요)
    # token = oauth_login()
    # if not token:
    #     print("OAuth login failed")
    #     return
    
    # 옵션 2: 기존 토큰 사용 (public 레포만 가능)
    token = GITHUB_TOKEN
    
    # 1. 레포지토리 ID 찾기
    print("\n--- Step 1: Find Repository ID ---")
    repo_id = get_repo_id_by_name(TEST_USER, TEST_REPO_NAME, token)
    if not repo_id:
        return
    
    # 2. 현재 사용자 정보
    print("\n--- Step 2: Get Current User ---")
    user_response = requests.get(f"{BASE_URL}/user", params={'token': token})
    if not check_response(user_response): return
    user_json = get_json_safely(user_response)
    if not user_json: return
    commitary_id = user_json.get("commitary_id")
    
    # 3. 브랜치 확인
    print("\n--- Step 3: Get Branches ---")
    branches_response = requests.get(f"{BASE_URL}/branches", params={
        'token': token,
        'repo_id': repo_id
    })
    if check_response(branches_response):
        branches_json = get_json_safely(branches_response)
        if branches_json:
            print("Available branches:")
            branches = branches_json.get('branchList', [])
            for branch in branches[:5]:
                print(f"  - {branch['name']}")
            
            # 기본 브랜치 선택
            default_branch = 'main' if any(b['name'] == 'main' for b in branches) else branches[0]['name']
            print(f"\nUsing branch: {default_branch}")
    
    # 4. 최근 커밋 확인
    print("\n--- Step 4: Check Recent Commits ---")
    # 최근 30일
    end_date = "2025-09-30T23:59:59Z"
    start_date = "2025-09-01T00:00:00Z"
    
    commits_response = requests.get(f"{BASE_URL}/githubCommits2", params={
        'token': token,
        'repo_id': repo_id,
        'branch_name': default_branch,
        'datetime_from': start_date,
        'datetime_to': end_date
    })
    
    if check_response(commits_response):
        commits_json = get_json_safely(commits_response)
        if commits_json:
            commits = commits_json.get('commitList', [])
            print(f"Found {len(commits)} commits in last 30 days")
            
            if len(commits) > 0:
                print("\nRecent commits:")
                for commit in commits[:5]:
                    print(f"  - {commit['commit_datetime']}: {commit['commit_msg'][:60]}")
                
                # 5. 인사이트 생성
                print("\n--- Step 5: Create Insight ---")
                # 날짜 형식 변환 필요
                from datetime import datetime

                # GitHub API 날짜를 파싱
                latest_commit_datetime_str = commits[0]['commit_datetime']
                # "Mon, 29 Sep 2025 10:22:46 GMT" 형식을 파싱
                latest_commit_dt = datetime.strptime(latest_commit_datetime_str, "%a, %d %b %Y %H:%M:%S %Z")

                # ISO 8601 형식으로 변환
                latest_commit_date = latest_commit_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                print(f"Latest commit date (converted): {latest_commit_date}")
                
                create_params = {
                    'token': token,
                    'repo_id': repo_id,
                    'commitary_id': commitary_id,
                    'date_from': latest_commit_date,
                    'branch': default_branch
                }
                
                create_response = requests.post(f"{BASE_URL}/createInsight", params=create_params)
                print(f"Create insight response: {create_response.status_code}")
                
                if create_response.status_code in [200, 201, 409]:
                    response_json = get_json_safely(create_response)
                    if response_json:
                        print(f"Message: {response_json.get('message')}")
                        
                # 6. 인사이트 조회
                print("\n--- Step 6: Retrieve Insights ---")
                get_params = {
                    'repo_id': repo_id,
                    'commitary_id': commitary_id,
                    'date_from': start_date,
                    'date_to': end_date
                }
                get_response = requests.get(f"{BASE_URL}/insights", params=get_params)
                if check_response(get_response):
                    insights_json = get_json_safely(get_response)
                    if insights_json:
                        insights = insights_json.get('insights', [])
                        print(f"Found {len(insights)} insights")
                        for insight in insights[:3]:
                            if insight.get('activity'):
                                print(f"\n  Date: {insight['date_of_insight']}")
                                print(f"  Activity: {insight['activity']}")
                                print(f"  Items: {len(insight.get('items', []))}")
            else:
                print("No commits found in the last 30 days")


# --- Main Execution ---
if __name__ == "__main__":
    if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_PERSONAL_ACCESS_TOKEN":
        print("CRITICAL ERROR: GITHUB_TOKEN is not set. Please create a .env file or set it as an environment variable.")
    else:
        # Run all the tests
        # test_get_user()
        # test_get_repos()
        # test_get_branches()
        # test_get_diff()
        # test_get_commits()
        # test_get_commits2()
        # test_get_diff_invalid_datetime()
        # test_repo_lifecycle()
        #test_insight_lifecycle()
        test_other_user_repository()

        print("\nAll tests finished.")