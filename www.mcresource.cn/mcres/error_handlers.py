# mcres/error_handlers.py
from flask import render_template
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):

    @app.errorhandler(Exception)
    def unhandled_error(e):
        """兜住所有未被处理的异常。

        原先这里注册的是 ``@app.errorhandler(500)``，Flask 会把它当作
        HTTPException 处理器，只有框架自己抛的 InternalServerError 才会命中；
        真正的未捕获异常走的是 ``handle_exception``，用户看到的是 Werkzeug
        默认错误页，站点的 errors/500.html 从来没有生效过。

        改为 ``errorhandler(Exception)`` 后：
        · HTTPException 子类（403/404/405…）原样返回，交给下面的按状态码
          处理器或 Flask 默认逻辑，不会被误判成 500；
        · 其余异常记录完整堆栈并渲染站点的 500 页面。
        """
        if isinstance(e, HTTPException):
            return e
        app.logger.error('未处理异常', exc_info=e)
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
