from flask import session
from flask_login import current_user
from models import Tree

def get_active_tree():
    if not current_user.is_authenticated:
        return None
    tree_id = session.get('active_tree_id')
    if tree_id:
        tree = Tree.query.get(tree_id)
        if tree and any(p.user_id == current_user.id for p in tree.permissions):
            return tree
    for perm in current_user.tree_permissions:
        if perm.role in ('owner', 'editor'):
            session['active_tree_id'] = perm.tree_id
            return perm.tree
    return None