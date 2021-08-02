import jwt
from base64 import b64decode
from flask import redirect
from flask import make_response
from flask import request
from flask import jsonify
from flask import session
from functools import wraps
from app import app
from .helpers import level_is_easy
from .helpers import level_is_hard

def run_only_once(resolve_func):
    @wraps(resolve_func)
    def wrapper(self, next, root, info, *args, **kwargs):
        has_context = info.context is not None
        decorator_name = "__{}_run__".format(self.__class__.__name__)

        if has_context:
            if isinstance(info.context, dict) and not info.context.get(decorator_name, False):
                info.context[decorator_name] = True
                return resolve_func(self, next, root, info, *args, **kwargs)
            elif not isinstance(info.context, dict) and not getattr(info.context, decorator_name, False):
                setattr(info.context, decorator_name, True)
                return resolve_func(self, next, root, info, *args, **kwargs)

        return next(root, info, *args, **kwargs)

    return wrapper


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None

        if 'Cookie' in request.headers:
            try:
                # Deliberately update the token in session on each call to this decorator
                # This adds weird session fixation conditions 
                session['jwt'] = request.headers.get('Cookie').split('=')[2] 
            except IndexError:
                return make_response(redirect('/'))
        
        # Deliberately vulnerable by only checking that a token is put in session
        # and failing to verify signature and expiry for granting authentication
        if not session.get('jwt'):
            return make_response(redirect('/'))

        return f(*args, **kwargs)
    return decorator


def access_controlled_for(allowed_roles='user'):
    def access_control(f):
        @wraps(f)
        def decorator(*args, **kwargs):
            if level_is_easy:
                # Deliberately vulnerable by not checking signature
                token = jwt.decode(session.get('jwt'), options={"verify_signature": False})
            if level_is_hard:
                try:
                    token = jwt.decode(session.get('jwt'), app.secret_key, algorithms="HS256") # Signature is checked
                    user_roles = token['prv'].split(',')
                except ValueError as err:
                    print('prv claim empty or absent in the jwt token. Defaulting to "user" role')
                    user_roles = ['user']
                except jwt.exceptions.InvalidSignatureError as err:
                    return make_response(redirect('/'))
            
            if not any(role in allowed_roles for role in user_roles):
                return make_response(redirect('/forbidden'))
            return f(*args, **kwargs)
        return decorator
    return access_control
