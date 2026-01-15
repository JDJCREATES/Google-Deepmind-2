"""
Remote provider service for managing cloud repositories.
Supports GitHub and extensible for other providers (GitLab, Bitbucket).
"""
import aiohttp
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.models.user import User

class RemoteProvider(ABC):
    """Abstract base class for remote git providers."""
    
    @abstractmethod
    async def create_repository(self, user: User, name: str, private: bool = True) -> Dict[str, Any]:
        """Create a new repository."""
        pass
    
    @abstractmethod
    async def check_remote_exists(self, user: User, owner: str, repo: str) -> bool:
        """Check if a remote repository exists and is accessible."""
        pass
        
    @abstractmethod
    async def get_user_repos(self, user: User) -> List[Dict[str, Any]]:
        """Get list of user's repositories."""
        pass

class GitHubProvider(RemoteProvider):
    """GitHub implementation of RemoteProvider."""
    
    BASE_URL = "https://api.github.com"
    
    def _get_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    async def create_repository(self, user: User, name: str, private: bool = True) -> Dict[str, Any]:
        token = user.get_github_token()
        if not token:
            raise ValueError("User has no GitHub token")
            
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/user/repos",
                headers=self._get_headers(token),
                json={
                    "name": name,
                    "private": private,
                    "auto_init": True,  # Create with README so it's ready to push
                    "description": "Created by Ships AI"
                }
            ) as resp:
                if resp.status == 201:
                    return await resp.json()
                error_text = await resp.text()
                raise Exception(f"Failed to create GitHub repo: {resp.status} {error_text}")

    async def check_remote_exists(self, user: User, owner: str, repo: str) -> bool:
        token = user.get_github_token()
        if not token:
            return False
            
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}",
                headers=self._get_headers(token)
            ) as resp:
                return resp.status == 200

    async def get_user_repos(self, user: User) -> List[Dict[str, Any]]:
        token = user.get_github_token()
        if not token:
            raise ValueError("User has no GitHub token")
            
        async with aiohttp.ClientSession() as session:
            # Pagination might be needed for full list, getting first 100
            async with session.get(
                f"{self.BASE_URL}/user/repos?sort=updated&per_page=100",
                headers=self._get_headers(token)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []

def get_remote_provider(type: str = "github") -> RemoteProvider:
    """Factory to get the appropriate remote provider."""
    if type == "github":
        return GitHubProvider()
    raise ValueError(f"Unknown provider type: {type}")
