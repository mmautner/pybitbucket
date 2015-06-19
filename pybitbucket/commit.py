from functools import partial

from uritemplate import expand

from pybitbucket.bitbucket import BitbucketBase, Client
from pybitbucket.user import User
from pybitbucket.repository import Repository


class Commit(BitbucketBase):
    id_attribute = 'hash'

    # Must override base constructor to account for approve and unapprove
    def __init__(self, data, client=Client()):
        self.data = data
        self.client = client
        self.__dict__.update(data)
        for link, body in data['links'].items():
            if link == 'clone':
                self.clone = {item['name']: item['href'] for item in body}
            elif link == 'approve':
                setattr(
                    self,
                    'approve',
                    partial(self.post_commit_approval, url=body['href']))
                setattr(
                    self,
                    'unapprove',
                    partial(self.delete_commit_approval, url=body['href']))
            else:
                for head, url in body.items():
                    setattr(
                        self,
                        link,
                        partial(self.client.remote_relationship, url=url))
        self.raw_author = self.author['raw']
        self.author = User(self.author['user'], client=client)
        self.repository = Repository(self.repository, client=client)

    @staticmethod
    def find_commit_in_repository_by_revision(
            username,
            repository_name,
            revision,
            client=Client()):
        template = (
            'https://{+bitbucket_url}' +
            '/2.0/repositories/{username}/{repository_name}' +
            '/commit/{revision}')
        url = expand(
            template,
            {
                'bitbucket_url': client.get_bitbucket_url(),
                'username': username,
                'repository_name': repository_name,
                'revision': revision
            })
        response = client.session.get(url)
        if 404 == response.status_code:
            return
        Client.expect_ok(response)
        return Commit(response.json(), client=client)

    @staticmethod
    def find_commit_in_repository_full_name_by_revision(
            repository_full_name,
            revision,
            client=Client()):
        if '/' not in repository_full_name:
            raise NameError(
                "Repository full name must be in the form: username/name")
        username, repository_name = repository_full_name.split('/')
        return Commit.find_commit_in_repository_by_revision(
            username,
            repository_name,
            revision,
            client=client)

    @staticmethod
    def find_commits_in_repository(
            username,
            repository_name,
            branch=None,
            include=[],
            exclude=[],
            client=Client()):
        template = (
            'https://{+bitbucket_url}' +
            '/2.0/repositories/{username}/{repository_name}' +
            '/commits{/branch}{?include*,exclude*}')
        url = expand(
            template,
            {
                'bitbucket_url': client.get_bitbucket_url(),
                'username': username,
                'repository_name': repository_name,
                'branch': branch,
                'include': include,
                'exclude': exclude
            })
        for commit in client.remote_relationship(url):
            yield commit

    @staticmethod
    def find_commits_in_repository_full_name(
            repository_full_name,
            branch=None,
            include=[],
            exclude=[],
            client=Client()):
        if '/' not in repository_full_name:
            raise NameError(
                "Repository full name must be in the form: username/name")
        username, repository_name = repository_full_name.split('/')
        yield Commit.find_commits_in_repository(
            username,
            repository_name,
            branch=branch,
            include=include,
            exclude=exclude,
            client=client)

    def post_commit_approval(self, url):
        response = self.client.session.post(url)
        Client.expect_ok(response)
        json_data = response.json()
        return json_data.get('approved')

    def delete_commit_approval(self, url):
        response = self.client.session.delete(url)
        # Deletes the approval and returns 204 (No Content).
        Client.expect_ok(response, 204)
        return True

    @staticmethod
    def is_type(data):
        return data.get('hash')


Client.bitbucket_types.add(Commit)
