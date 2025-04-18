def assert_message(message, expected_code, *message_contains):
    assert message.code == expected_code
    for string in message_contains:
        assert string in message.message
