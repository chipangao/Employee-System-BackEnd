import sys
import traceback
from flask import abort

# def abort_msg(e):
#     """500 bad request for exception"""
#     error_class = e.__class__.__name__
#     detail = e.args[0]
#     cl, exc, tb = sys.exc_info()
#     lastCallStack = traceback.extract_tb(tb)[-1]
#     fileName = lastCallStack[0]
#     lineNum = lastCallStack[1]
#     funcName = lastCallStack[2]
#     errMsg = "Exception raise in file: {}, line {}, in {}: [{}] {}.".format(
#         fileName, lineNum, funcName, error_class, detail)
#     print(errMsg)
#     abort(500, errMsg)

def abort_msg(e):
    """Custom error handler that formats all error messages consistently"""
    try:
        # Handle cases where exception might not have args
        detail = str(e.args[0]) if e.args else str(e)
    except Exception:
        detail = str(e)
    
    # Your existing error response logic
    return {
        'success': False,
        'message': 'An error occurred',
        'detail': detail
    }, getattr(e, 'code', 500)