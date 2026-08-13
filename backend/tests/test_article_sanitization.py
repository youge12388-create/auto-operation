# ruff: noqa: E501 - long escaped Unicode fixtures are clearer as a single literal.
from content_ops.workflow import _require_article_body


def test_skill_byline_and_contact_are_stripped_from_article_body():
    article = "# \u6b63\u6587\n\n" + "\u8fd9\u662f\u5b8c\u6574\u3001\u53ef\u53d1\u5e03\u7684\u6587\u7ae0\u6b63\u6587\u3002" * 50
    byline = (
        "\n\n> / \u4f5c\u8005\uff1a\u5361\u5179\u514b"
        "\n> / \u6295\u7a3f\u6216\u7206\u6599\uff0c\u8bf7\u8054\u7cfb\u90ae\u7bb1\uff1awriter@example.com"
    )

    assert _require_article_body(article + byline, "rewrite") == article