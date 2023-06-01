from .lib import update_global_session_from_doc


def on_document_changed():
    """On workfile change callback"""
    update_global_session_from_doc()
