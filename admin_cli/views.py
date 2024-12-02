# # encoding: utf-8
#
# from flask import Blueprint
# import click
# from user_service.models.role import RoleModel
# from user_service.models.user import UserModel
# from datetime import datetime as _time
# from user_service.libs.decorators import error_handler_decorator
#
#
#
# blueprint = Blueprint('admin_cli', __name__)
#
# red_text = "\033[91m"
# green_text = "\033[92m"
# reset_color = "\033[0m"
#
#
#
# @blueprint.cli.command('add-role')
# @click.option('--username', '-u', type=str, help='Username', required=True)
# @click.option('--email', '-e', type=str, help='The user email', required=False)
# @click.option('--id', '-i', type=str, help='Target object id (ontology id, collection id, system)', required=True)
# @click.option('--type', '-t', type=str, help='Target object type (ontology, collection, system)', required=True)
# @click.option('--role', '-r', type=str, help='Role to assign.', required=True)
# @click.option('--client', '-c', type=str, help='The target client system (general, nfdi4chem, nfdi4ing)', required=True)
# @error_handler_decorator
# def assign_role(username, email, id, type, role, client):
#     user_id = UserModel.get_user_id_by_username(username=username, client_ts=client)
#     if not user_id:
#         text = "Failed: Username does not exist!"        
#         print (f"{red_text}{text}{reset_color}")
#         return True        
#
#     role_model = RoleModel(
#         user_id=user_id,
#         target_object_id=id,
#         target_object_type=type,
#         role=role,
#         created_at=_time.now(),
#         client=client,
#         email=email
#     )    
#     if not role_model.role_is_valid():
#         text = "Failed: Role is not valid!"        
#         print (f"{red_text}{text}{reset_color}")
#         return True
#
#     role_model.register_role()
#     text = "Role has been added!"
#     print (f"{green_text}{text}{reset_color}")
#     return True
#
#
#
#
# @blueprint.cli.command("get-roles")
# @click.option('--username', '-u', type=str, help='Username', required=True)
# @click.option('--client', '-c', type=str, help='The target client system (general, nfdi4chem, nfdi4ing)', required=True)
# @error_handler_decorator
# def get_roles_for_user(username, client):
#     user_id = UserModel.get_user_id_by_username(username=username, client_ts=client)
#     if not user_id:
#         text = "Failed: Username does not exist!"        
#         print (f"{red_text}{text}{reset_color}")
#         return True
#
#     role_model = RoleModel(user_id=user_id)
#     role_records = role_model.get_by_user()
#     if not role_records:
#         print("No role found!")
#         return True
#     for record in role_records:
#         print("{}: {} ({}) in client {}".format(record.role, record.target_object_id, record.target_object_type, record.client_ts))
#
#     return True
#
#
#
# @blueprint.cli.command("revoke-role")
# @click.option('--username', '-u', type=str, help='Username', required=True)
# @click.option('--id', '-i', type=str, help='Target object id (ontology id, collection id, system)', required=True)
# @click.option('--client', '-c', type=str, help='The target client system (general, nfdi4chem, nfdi4ing)', required=True)
# @error_handler_decorator
# def revoke_role_for_user(username, id, client):
#     user_id = UserModel.get_user_id_by_username(username=username, client_ts=client)
#     if not user_id:
#         text = "Failed: Username does not exist!"        
#         print (f"{red_text}{text}{reset_color}")
#         return True
#
#     role_model = RoleModel(user_id=user_id, target_object_id=id, client=client)
#     role_deleted = role_model.delete_user_role()
#     if not role_deleted:
#         print("No role found to revoke!")
#         return True
#
#     text = "Role is Revoked!"        
#     print (f"{green_text}{text}{reset_color}")
#
#     return True
#
#
#
# @blueprint.cli.command("user-list")
# @error_handler_decorator
# def user_list():
#     users = UserModel.get_all_users()    
#     for user in users:
#         if user.is_active:
#             print(user.username)
#     return True
#
#
#
