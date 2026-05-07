import base64
from github import Github, GithubException

def push_to_github(repo_name: str, files_dict: dict, token: str) -> dict:
    """
    Creates a GitHub repository if it doesn't exist and pushes files to it.

    Args:
        repo_name (str): Name of the repository.
        files_dict (dict): Dictionary mapping file paths to file contents (strings).
        token (str): GitHub personal access token.

    Returns:
        dict: {'success': bool, 'repo_url': str, 'message': str}
    """
    try:
        g = Github(token)
        user = g.get_user()

        # Check if repository exists, create if not
        try:
            repo = user.get_repo(repo_name)
            created = False
        except GithubException as e:
            if e.status == 404:
                repo = user.create_repo(repo_name, private=False)
                created = True
            else:
                raise

        default_branch = repo.default_branch  # 'main' or 'master'

        # Push each file (create or update)
        for file_path, content in files_dict.items():
            try:
                repo.create_file(file_path, f"Add {file_path}", content, branch=default_branch)
            except GithubException as e:
                if e.status == 422:  # File already exists -> update it
                    contents = repo.get_contents(file_path, ref=default_branch)
                    repo.update_file(
                        file_path,
                        f"Update {file_path}",
                        content,
                        contents.sha,
                        branch=default_branch
                    )
                else:
                    raise

        return {
            'success': True,
            'repo_url': repo.html_url,
            'message': (
                'Repository created and files pushed successfully'
                if created else
                'Files pushed to existing repository'
            )
        }
    except GithubException as e:
        return {
            'success': False,
            'repo_url': None,
            'message': f"GitHub error: {e.data.get('message', str(e))}"
        }
    except Exception as e:
        return {
            'success': False,
            'repo_url': None,
            'message': f"Error: {str(e)}"
        }