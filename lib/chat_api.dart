import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiConfig {
  const ApiConfig({required this.endpoint, required this.token});

  final String endpoint;
  final String token;
}

class SearchResult {
  const SearchResult({required this.title, required this.snippet, required this.url});
  final String title;
  final String snippet;
  final String url;
}

class SearchReply {
  const SearchReply({required this.results, required this.provider});
  final List<SearchResult> results;
  final String provider;
  String get formattedText {
    if (results.isEmpty) return 'لم يُعثر على نتائج في ويكيبيديا لهذا الاستعلام.';
    return results.asMap().entries.map((entry) {
      final item = entry.value;
      return '${entry.key + 1}. ${item.title}\n${item.snippet}\n${item.url}';
    }).join('\n\n');
  }
}

class ChatReply {
  const ChatReply({required this.content, required this.provider});

  final String content;
  final String provider;
}

class ChatApi {
  ChatApi({http.Client? client, FlutterSecureStorage? storage})
      : _client = client ?? http.Client(),
        _storage = storage ?? const FlutterSecureStorage();

  static const _endpointKey = 'api_endpoint';
  static const _tokenKey = 'api_access_token';
  final http.Client _client;
  final FlutterSecureStorage _storage;

  String? validateConfig(String endpoint, String token) {
    final value = endpoint.trim();
    final uri = Uri.tryParse(value);
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.isEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      return 'أدخل رابط HTTPS صحيحاً للخادم.';
    }
    if (token.trim().length < 16) {
      return 'مفتاح الوصول غير صالح أو قصير جداً.';
    }
    return null;
  }

  Future<ApiConfig?> loadConfig() async {
    final endpoint = await _storage.read(key: _endpointKey);
    final token = await _storage.read(key: _tokenKey);
    if (endpoint == null || token == null) return null;
    if (validateConfig(endpoint, token) != null) return null;
    return ApiConfig(endpoint: endpoint, token: token);
  }

  Future<void> saveConfig({
    required String endpoint,
    required String token,
  }) async {
    final error = validateConfig(endpoint, token);
    if (error != null) throw ArgumentError(error);
    await _storage.write(key: _endpointKey, value: endpoint.trim().replaceFirst(RegExp(r'/+$'), ''));
    await _storage.write(key: _tokenKey, value: token.trim());
  }

  static const int maxMessages = 50;
  static const int maxMessageChars = 16000;
  static const int maxTotalChars = 48000;

  /// Keeps system instructions and the newest conversation turns within the
  /// Worker's strict request limits without changing the on-screen transcript.
  static List<Map<String, String>> prepareMessages(
    List<Map<String, String>> messages,
  ) {
    final systems = messages.where((m) => m['role'] == 'system').toList();
    final conversation = messages.where((m) => m['role'] != 'system').toList();
    final result = <Map<String, String>>[];
    var remaining = maxTotalChars;

    for (final message in systems.take(2)) {
      final content = message['content'] ?? '';
      if (content.isEmpty || remaining <= 0) continue;
      final bounded = content.length > maxMessageChars
          ? content.substring(0, maxMessageChars)
          : content;
      final accepted = bounded.length > remaining
          ? bounded.substring(0, remaining)
          : bounded;
      if (accepted.isNotEmpty) {
        result.add({'role': 'system', 'content': accepted});
        remaining -= accepted.length;
      }
    }

    final selected = <Map<String, String>>[];
    for (final message in conversation.reversed) {
      if (selected.length + result.length >= maxMessages || remaining <= 0) {
        break;
      }
      final role = message['role'];
      final content = message['content'] ?? '';
      if ((role != 'user' && role != 'assistant') || content.isEmpty) continue;
      final allowed = [
        maxMessageChars,
        remaining,
      ].reduce((a, b) => a < b ? a : b);
      final accepted = content.length > allowed
          ? content.substring(0, allowed)
          : content;
      if (accepted.isEmpty) continue;
      selected.add({'role': role!, 'content': accepted});
      remaining -= accepted.length;
    }

    return [...result, ...selected.reversed];
  }

  Future<int> checkConnection({required ApiConfig config}) async {
    final response = await _client.get(
      Uri.parse('${config.endpoint}/v1/providers/status'),
      headers: {'authorization': 'Bearer ${config.token}'},
    ).timeout(const Duration(seconds: 12));
    Map<String, dynamic> data;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      data = decoded;
    } on FormatException {
      throw const ChatApiException('استجابة فحص الخادم غير مفهومة.');
    }
    if (response.statusCode < 200 || response.statusCode >= 300 || data['ok'] != true) {
      final code = data['error'];
      throw ChatApiException(_messageForCode(code is String ? code : 'server_error'));
    }
    final providers = data['providers'];
    if (providers is! List) throw const ChatApiException('بيانات حالة المحركات غير صالحة.');
    return providers.where((item) => item is Map && item['enabled'] == true).length;
  }

  Future<ChatReply> send({
    required ApiConfig config,
    required List<Map<String, String>> messages,
  }) async {
    final boundedMessages = prepareMessages(messages);
    if (boundedMessages.isEmpty) {
      throw const ChatApiException('لا توجد رسالة صالحة للإرسال.');
    }
    final uri = Uri.parse('${config.endpoint}/v1/chat');
    final lastUserIndex = boundedMessages.lastIndexWhere((item) => item['role'] == 'user');
    if (lastUserIndex < 0) {
      throw const ChatApiException('أضف رسالة مستخدم قبل الإرسال.');
    }
    final userPrompt = boundedMessages[lastUserIndex]['content']!;
    final history = boundedMessages
        .where((item) => item['role'] != 'system')
        .toList();
    if (history.isNotEmpty) history.removeLast();
    final response = await _client
        .post(
          uri,
          headers: {
            'content-type': 'application/json',
            'authorization': 'Bearer ${config.token}',
          },
          // The deployed v2.2.0 Worker uses the singular message contract.
          // Keep messages as well for compatibility with the newer Worker API.
          body: jsonEncode({
            'message': userPrompt,
            'history': history,
            'messages': boundedMessages,
          }),
        )
        .timeout(const Duration(seconds: 65));

    final Map<String, dynamic> data;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      data = decoded;
    } on FormatException {
      throw const ChatApiException('استجابة الخادم غير مفهومة.');
    }

    if (response.statusCode < 200 || response.statusCode >= 300 || data['ok'] != true) {
      final code = data['error'];
      throw ChatApiException(_messageForCode(code is String ? code : 'server_error'));
    }

    final rawMessage = data['message'];
    final candidates = <dynamic>[
      rawMessage is Map ? rawMessage['content'] : rawMessage,
      data['reply'],
      data['response'],
      data['text'],
    ];
    String? content;
    for (final candidate in candidates) {
      if (candidate is String && candidate.trim().isNotEmpty) {
        content = candidate.trim();
        break;
      }
    }
    if (content == null) {
      throw const ChatApiException('وصل رد فارغ أو غير مدعوم من الخادم.');
    }
    return ChatReply(
      content: content,
      provider: data['provider'] is String ? data['provider'] as String : 'AI',
    );
  }

  Future<SearchReply> search({required ApiConfig config, required String query}) async {
    final normalized = query.trim();
    if (normalized.length < 2 || normalized.length > 200) throw const ChatApiException('اكتب عبارة بحث بين حرفين و200 حرف.');
    final response = await _client.post(
      Uri.parse('${config.endpoint}/v1/search'),
      headers: {'content-type': 'application/json', 'authorization': 'Bearer ${config.token}'},
      body: jsonEncode({'query': normalized}),
    ).timeout(const Duration(seconds: 15));
    final Map<String, dynamic> data;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      data = decoded;
    } on FormatException { throw const ChatApiException('استجابة البحث غير مفهومة.'); }
    if (response.statusCode < 200 || response.statusCode >= 300 || data['ok'] != true) {
      final code = data['error'];
      throw ChatApiException(_messageForCode(code is String ? code : 'search_error'));
    }
    final results = <SearchResult>[];
    final raw = data['results'];
    if (raw is List) {
      for (final item in raw.take(5)) {
        if (item is! Map) continue;
        final title = item['title'], snippet = item['snippet'], url = item['url'];
        final uri = url is String ? Uri.tryParse(url) : null;
        final host = uri?.host ?? '';
        final trustedHost = host == 'wikipedia.org' || host.endsWith('.wikipedia.org');
        if (title is String && snippet is String && url is String && uri != null && uri.scheme == 'https' && trustedHost) {
          results.add(SearchResult(title: title, snippet: snippet, url: url));
        }
      }
    }
    return SearchReply(results: results, provider: data['provider'] is String ? data['provider'] as String : 'Wikipedia');
  }
  String _messageForCode(String code) {
    switch (code.toLowerCase()) {
      case 'unauthorized':
        return 'مفتاح الوصول غير صحيح. راجع إعدادات الاتصال.';
      case 'server_auth_not_configured':
        return 'لم يتم إعداد حماية الخادم بعد.';
      case 'no_free_provider_configured':
        return 'لا يوجد محرك مفعّل حالياً. أضف محركاً وتحقق من شروط استخدامه المجاني أولاً.';
      case 'all_providers_failed':
        return 'تعذر الاتصال بالمحركات حالياً. تحقق من المفاتيح والحصة والاتصال.';
      case 'invalid_search_query':
        return 'عبارة البحث غير صالحة. استخدم من حرفين إلى 200 حرف.';
      case 'search_provider_unavailable':
      case 'search_provider_invalid_response':
        return 'تعذر الوصول إلى خدمة البحث حالياً. حاول مجدداً.';
      case 'request_too_large':
        return 'الطلب أكبر من الحد المسموح.';
      default:
        return 'تعذر إكمال الطلب. حاول مجدداً لاحقاً.';
    }
  }

  String userMessageFor(Object error) {
    if (error is ChatApiException) return error.message;
    if (error is http.ClientException) return 'تعذر الوصول إلى الخادم. تحقق من الإنترنت ورابط الخادم.';
    if (error is ArgumentError) return error.message.toString();
    return 'حدث خطأ أثناء الاتصال بالخادم. تحقق من إعدادات الاتصال.';
  }
}

class ChatApiException implements Exception {
  const ChatApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
