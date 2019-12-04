from argparse import ArgumentParser
from getpass import getpass
import os

from transformers.commands import BaseTransformersCLICommand
from transformers.hf_api import HfApi, HfFolder, HTTPError


class UserCommands(BaseTransformersCLICommand):
    @staticmethod
    def register_subcommand(parser: ArgumentParser):
        login_parser = parser.add_parser('login')
        login_parser.set_defaults(func=lambda args: LoginCommand(args))
        whoami_parser = parser.add_parser('whoami')
        whoami_parser.set_defaults(func=lambda args: WhoamiCommand(args))
        logout_parser = parser.add_parser('logout')
        logout_parser.set_defaults(func=lambda args: LogoutCommand(args))
        list_parser = parser.add_parser('ls')
        list_parser.set_defaults(func=lambda args: ListObjsCommand(args))
        # upload
        upload_parser = parser.add_parser('upload')
        upload_parser.add_argument('file', type=str, help='Local filepath of the file to upload.')
        upload_parser.add_argument('--filename', type=str, default=None, help='Optional: override object filename on S3.')
        upload_parser.set_defaults(func=lambda args: UploadCommand(args))



class BaseUserCommand:
    def __init__(self, args):
        self.args = args
        self._api = HfApi()


class LoginCommand(BaseUserCommand):
    def run(self):
        print("""
        _|    _|  _|    _|    _|_|_|    _|_|_|  _|_|_|  _|      _|    _|_|_|      _|_|_|_|    _|_|      _|_|_|  _|_|_|_|  
        _|    _|  _|    _|  _|        _|          _|    _|_|    _|  _|            _|        _|    _|  _|        _|        
        _|_|_|_|  _|    _|  _|  _|_|  _|  _|_|    _|    _|  _|  _|  _|  _|_|      _|_|_|    _|_|_|_|  _|        _|_|_|    
        _|    _|  _|    _|  _|    _|  _|    _|    _|    _|    _|_|  _|    _|      _|        _|    _|  _|        _|        
        _|    _|    _|_|      _|_|_|    _|_|_|  _|_|_|  _|      _|    _|_|_|      _|        _|    _|    _|_|_|  _|_|_|_|  

        """)
        username = input("Username: ")
        password = getpass()
        try:
            token = self._api.login(username, password)
        except HTTPError as e:
            # probably invalid credentials, display error message.
            print(e)
            exit(1)
        HfFolder.save_token(token)
        print("Login successful")
        print("Your token:", token, "\n")
        print("Your token has been saved to", HfFolder.path_token)


class WhoamiCommand(BaseUserCommand):
    def run(self):
        token = HfFolder.get_token()
        if token is None:
            print("Not logged in")
            exit()
        try:
            user = self._api.whoami(token)
            print(user)
        except HTTPError as e:
            print(e)


class LogoutCommand(BaseUserCommand):
    def run(self):
        token = HfFolder.get_token()
        if token is None:
            print("Not logged in")
            exit()
        HfFolder.delete_token()
        self._api.logout(token)
        print("Successfully logged out.")


class ListObjsCommand(BaseUserCommand):
    def run(self):
        token = HfFolder.get_token()
        if token is None:
            print("Not logged in")
            exit(1)
        try:
            objs = self._api.list_objs(token)
        except HTTPError as e:
            print(e)
            exit(1)
        if len(objs) == 0:
            print("No shared file yet")
        for obj in objs:
            print(
                obj.filename,
                obj.LastModified,
                obj.ETag,
                obj.Size
            )


class UploadCommand(BaseUserCommand):
    def run(self):
        token = HfFolder.get_token()
        if token is None:
            print("Not logged in")
            exit(1)
        filepath = os.path.join(os.getcwd(), self.args.file)
        filename = self.args.filename if self.args.filename is not None else os.path.basename(filepath)
        print("About to upload file {} to S3 under filename {}".format(filepath, filename))
        choice = input("Proceed? [Y/n] ").lower()
        if not(choice == "" or choice == "y" or choice == "yes"):
            print("Abort")
            exit()
        print("Uploading...")
        access_url = self._api.presign_and_upload(
            token=token, filename=filename, filepath=filepath
        )
        print("Your file now lives at:")
        print(access_url)
