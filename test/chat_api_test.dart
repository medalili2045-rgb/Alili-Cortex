import 'dart:convert';

import 'package:alili_cortex/chat_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ChatApi conversation window', () {
    test('keeps the newest turns and stays within the worker message limit', () {
      final messages = List.generate(
        70,
        (index) => {
          'role': index.isEven ? 'user' : 'assistant',
          'content': 'message-$index',
        },
      );
      final prepared = ChatApi.prepareMessages(messages);

      expect(prepared.length, 50);
      expect(prepared.last['content'], 'message-69');
      expect(prepared.first['content'], 'message-20');
    });

    test('preserves system instructions and enforces per-message and total limits', () {
      final prepared = ChatApi.prepareMessages([
        {'role': 'system', 'content': 'instructions'},
        {'role': 'user', 'content': List.filled(20000, 'a').join()},
        {'role': 'assistant', 'content': List.filled(20000, 'b').join()},
        {'role': 'user', 'content': 'latest'},
      ]);

      expect(prepared.first['role'], 'system');
      expect(prepared.last['content'], 'latest');
      expect(prepared.every((m) => m['content']!.length <= 16000), isTrue);
      expect(
        prepared.fold<int>(0, (sum, m) => sum + m['content']!.length),
        lessThanOrEqualTo(48000),
      );
    });
  });
  group('ChatApi configuration validation', () {
    test('accepts an HTTPS Worker URL and a sufficiently long token', () {
      final api = ChatApi();
      expect(
        api.validateConfig(
          'https://alili-cortex-api.example.workers.dev',
          'this-is-a-long-enough-private-token',
        ),
        isNull,
      );
    });

    test('rejects insecure HTTP endpoints', () {
      final api = ChatApi();
      expect(
        api.validateConfig('http://example.workers.dev', 'this-is-a-long-enough-private-token'),
        isNotNull,
      );
    });

    test('rejects URLs containing query strings or fragments', () {
      final api = ChatApi();
      expect(
        api.validateConfig(
          'https://example.workers.dev/?token=leak',
          'this-is-a-long-enough-private-token',
        ),
        isNotNull,
      );
      expect(
        api.validateConfig(
          'https://example.workers.dev/#fragment',
          'this-is-a-long-enough-private-token',
        ),
        isNotNull,
      );
    });

    test('rejects short access tokens', () {
      final api = ChatApi();
      expect(api.validateConfig('https://example.workers.dev', 'short'), isNotNull);
    });
  });


  group('ChatApi connection diagnostics', () {
    test('checks authenticated provider status on the existing Worker route', () async {
      final api = ChatApi(client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/v1/providers/status');
        expect(request.headers['authorization'], 'Bearer this-is-a-long-enough-private-token');
        return http.Response(
          jsonEncode({
            'ok': true,
            'providers': [
              {'provider': 'cloudflare', 'enabled': true},
              {'provider': 'gemini', 'enabled': false},
            ],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }));
      final count = await api.checkConnection(
        config: const ApiConfig(
          endpoint: 'https://alili-cortex.medalili2045.workers.dev',
          token: 'this-is-a-long-enough-private-token',
        ),
      );
      expect(count, 1);
    });
  });

  group('ChatApi legacy Worker v2 compatibility', () {
    test('sends both v2 message and newer messages fields and accepts reply response', () async {
      final api = ChatApi(client: MockClient((request) async {
        expect(request.url.path, '/v1/chat');
        expect(request.headers['authorization'], 'Bearer this-is-a-long-enough-private-token');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['message'], 'أهلاً');
        expect(body['messages'], isA<List>());
        expect(body['history'], isEmpty);
        return http.Response(
          jsonEncode({'ok': true, 'provider': 'cloudflare', 'reply': 'مرحباً بك'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      }));
      final reply = await api.send(
        config: const ApiConfig(
          endpoint: 'https://alili-cortex.medalili2045.workers.dev',
          token: 'this-is-a-long-enough-private-token',
        ),
        messages: [
          {'role': 'user', 'content': 'أهلاً'},
        ],
      );
      expect(reply.content, 'مرحباً بك');
      expect(reply.provider, 'cloudflare');
    });
  });

  group('ChatApi search', () {
    test('parses bounded Wikipedia results from the authenticated endpoint', () async {
      final api = ChatApi(client: MockClient((request) async {
        expect(request.url.path, '/v1/search');
        expect(request.headers['authorization'], 'Bearer this-is-a-long-enough-private-token');
        expect(jsonDecode(request.body)['query'], 'الذكاء الاصطناعي');
        return http.Response.bytes(
          utf8.encode(jsonEncode({
            'ok': true,
            'provider': 'wikipedia',
            'results': [
              {'title': 'عنوان', 'snippet': 'ملخص', 'url': 'https://ar.wikipedia.org/wiki/عنوان'},
              {'title': 'رابط غير موثوق', 'snippet': 'تجاهل', 'url': 'https://evilwikipedia.org/wiki/x'},
            ],
          })),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }));
      final reply = await api.search(
        config: const ApiConfig(endpoint: 'https://api.example.workers.dev', token: 'this-is-a-long-enough-private-token'),
        query: 'الذكاء الاصطناعي',
      );
      expect(reply.provider, 'wikipedia');
      expect(reply.results.length, 1);
      expect(reply.results.single.title, 'عنوان');
      expect(reply.formattedText, contains('https://ar.wikipedia.org/wiki/عنوان'));
    });
  });
}