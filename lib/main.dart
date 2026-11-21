import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'chat_api.dart';

void main() => runApp(const AliliCortexApp());

class AliliCortexApp extends StatelessWidget {
  const AliliCortexApp({super.key});

  @override
  Widget build(BuildContext context) {
    const blue = Color(0xFF3478F6);
    return MaterialApp(
      title: 'Alili Cortex',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: blue),
        scaffoldBackgroundColor: const Color(0xFFF8FAFD),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFF8FAFD),
          surfaceTintColor: Colors.transparent,
          elevation: 0,
        ),
      ),
      home: const ChatHomePage(),
    );
  }
}

class ChatHomePage extends StatefulWidget {
  const ChatHomePage({super.key});

  @override
  State<ChatHomePage> createState() => _ChatHomePageState();
}

class _ChatHomePageState extends State<ChatHomePage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_ChatMessage> _messages = [];
  final ChatApi _chatApi = ChatApi();
  bool _busy = false;
  int _chatGeneration = 0;
  final List<_PickedAttachment> _attachments = [];
  bool _search = false;
  bool _thinking = false;
  bool _execution = false;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final value = _input.text.trim();

    if (_attachments.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('إرسال المرفقات غير متاح بعد. لن يتم إرسال الرسالة أو المرفقات.'),
        ),
      );
      return;
    }
    if (value.isEmpty || _busy) return;
    if (_execution) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('التنفيذ الآمن للمشاريع لم يُفعّل بعد.')),
      );
      return;
    }

    final generation = _chatGeneration;
    setState(() {
      _messages.add(_ChatMessage(role: 'user', content: value));
      _input.clear();
      _busy = true;
    });
    _scrollToLatest();

    try {
      final config = await _chatApi.loadConfig();
      if (config == null) {
        if (mounted && generation == _chatGeneration) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('افتح إعدادات الاتصال وأدخل رابط الخادم ومفتاح الوصول أولاً.')),
          );
        }
        return;
      }

      if (_search) {
        final result = await _chatApi.search(config: config, query: value);
        if (!mounted || generation != _chatGeneration) return;
        setState(() {
          _messages.add(_ChatMessage(
            role: 'assistant',
            content: '${result.formattedText}\n\nالمصدر: ويكيبيديا — هذا بحث معرفي محدود وليس بحثاً شاملاً في الويب.',
            provider: result.provider,
          ));
        });
        _scrollToLatest();
        return;
      }
      final history = <Map<String, String>>[
        if (_thinking)
          {
            'role': 'system',
            'content': 'أجب بعناية وعمق، تحقق من الافتراضات، ونظم الحل. لا تكشف التفكير الداخلي؛ قدم النتيجة والأسباب المفيدة فقط.',
          },
        ..._messages.map((message) => {
          'role': message.role,
          'content': message.content,
        }),
      ];

      final reply = await _chatApi.send(
        config: config,
        messages: history,
      );
      if (!mounted || generation != _chatGeneration) return;
      setState(() {
        _messages.add(_ChatMessage(
          role: 'assistant',
          content: reply.content,
          provider: reply.provider,
        ));
      });
      _scrollToLatest();
    } catch (error) {
      if (!mounted || generation != _chatGeneration) return;
      setState(() {
        _messages.add(_ChatMessage(
          role: 'assistant',
          content: _chatApi.userMessageFor(error),
        ));
      });
      _scrollToLatest();
    } finally {
      if (mounted && generation == _chatGeneration) {
        setState(() => _busy = false);
      }
    }
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _openConnectionSettings() async {
    final current = await _chatApi.loadConfig();
    if (!mounted) return;
    final endpointController = TextEditingController(text: current?.endpoint ?? 'https://alili-cortex.medalili2045.workers.dev');
    final tokenController = TextEditingController(text: current?.token ?? '');
    String? validationError;
    bool checkingConnection = false;
    String? connectionMessage;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('إعدادات الاتصال'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'أدخل عنوان Cloudflare Worker ومفتاح الوصول الخاص بك. تُحفظ البيانات في التخزين الآمن على الهاتف ولا تُرفع إلى GitHub.',
                  style: TextStyle(fontSize: 13, height: 1.5),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: endpointController,
                  keyboardType: TextInputType.url,
                  decoration: const InputDecoration(
                    labelText: 'رابط الخادم',
                    hintText: 'https://your-worker.workers.dev',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: tokenController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'مفتاح الوصول',
                  ),
                ),
                if (validationError != null) ...[
                  const SizedBox(height: 8),
                  Text(validationError!, style: const TextStyle(color: Colors.red)),
                ],
                if (connectionMessage != null) ...[
                  const SizedBox(height: 8),
                  Text(connectionMessage!, style: TextStyle(
                    color: connectionMessage!.startsWith('الاتصال ناجح') || connectionMessage!.startsWith('الخادم متصل') ? const Color(0xFF16834A) : Colors.red,
                    fontSize: 12,
                  )),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: checkingConnection ? null : () async {
                final error = _chatApi.validateConfig(endpointController.text, tokenController.text);
                if (error != null) { setDialogState(() { validationError = error; connectionMessage = null; }); return; }
                setDialogState(() { checkingConnection = true; validationError = null; connectionMessage = null; });
                try {
                  final ready = await _chatApi.checkConnection(config: ApiConfig(
                    endpoint: endpointController.text.trim().replaceFirst(RegExp(r'/+$'), ''),
                    token: tokenController.text.trim(),
                  ));
                  if (dialogContext.mounted) setDialogState(() { connectionMessage = ready == 0 ? 'الخادم متصل، لكن لا يوجد محرك ذكاء اصطناعي مفعّل.' : 'الاتصال ناجح. المحركات الجاهزة: $ready'; });
                } catch (error) {
                  if (dialogContext.mounted) setDialogState(() => connectionMessage = _chatApi.userMessageFor(error));
                } finally {
                  if (dialogContext.mounted) setDialogState(() => checkingConnection = false);
                }
              },
              child: checkingConnection ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('اختبار الاتصال'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('إلغاء'),
            ),
            TextButton(
              onPressed: () async {
                final error = _chatApi.validateConfig(
                  endpointController.text,
                  tokenController.text,
                );
                if (error != null) {
                  setDialogState(() => validationError = error);
                  return;
                }
                await _chatApi.saveConfig(
                  endpoint: endpointController.text,
                  token: tokenController.text,
                );
                if (dialogContext.mounted) Navigator.pop(dialogContext);
                if (mounted) {
                  ScaffoldMessenger.of(this.context).showSnackBar(
                    const SnackBar(content: Text('تم حفظ إعدادات الاتصال على هذا الجهاز.')),
                  );
                }
              },
              child: const Text('حفظ'),
            ),
          ],
        ),
      ),
    );
    endpointController.dispose();
    tokenController.dispose();
  }

  void _newChat() {
    _chatGeneration++;
    setState(() {
      _busy = false;
      _messages.clear();
      _attachments.clear();
    });
    _input.clear();
  }

  void _showAttachmentOptions() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.photo_outlined),
                title: const Text('الصور'),
                onTap: () {
                  Navigator.pop(sheetContext);
                  _pickImages();
                },
              ),
              ListTile(
                leading: const Icon(Icons.insert_drive_file_outlined),
                title: const Text('الملفات'),
                onTap: () {
                  Navigator.pop(sheetContext);
                  _pickFiles();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _pickImages() async {
    try {
      final images = await ImagePicker().pickMultiImage(imageQuality: 85);
      if (!mounted || images.isEmpty) return;
      setState(() {
        for (final image in images) {
          _attachments.add(_PickedAttachment(
            name: image.name,
            path: image.path,
            isImage: true,
          ));
        }
      });
    } catch (_) {
      if (mounted) _showPickerError();
    }
  }

  Future<void> _pickFiles() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: true,
        withData: false,
      );
      if (!mounted || result == null) return;
      setState(() {
        for (final file in result.files) {
          _attachments.add(_PickedAttachment(
            name: file.name,
            path: file.path,
            isImage: false,
          ));
        }
      });
    } catch (_) {
      if (mounted) _showPickerError();
    }
  }

  void _showPickerError() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('تعذر فتح منتقي الملفات. حاول مجدداً.')),
    );
  }

  void _removeAttachment(int index) {
    setState(() => _attachments.removeAt(index));
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          titleSpacing: 18,
          title: const Row(
            children: [
              _LogoMark(),
              SizedBox(width: 10),
              Text(
                'Alili Cortex',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          actions: [

            IconButton(
              tooltip: 'محادثة جديدة',
              onPressed: _newChat,
              icon: const Icon(Icons.edit_square),
            ),
            PopupMenuButton<String>(
              tooltip: 'المزيد',
              onSelected: (value) { if (value == 'connection') _openConnectionSettings(); },
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'connection', child: Row(children: [Icon(Icons.link_rounded, size: 19), SizedBox(width: 10), Text('الاتصال بالخادم')])),
              ],
            ),
            const SizedBox(width: 6),
          ],
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: _messages.isEmpty
                    ? _WelcomePanel(onPrompt: (value) {
                        _input.text = value;
                        _input.selection = TextSelection.collapsed(
                          offset: value.length,
                        );
                      })
                    : ListView.builder(
                        controller: _scroll,
                        padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) =>
                            _MessageBubble(
                              text: _messages[index].content,
                              isUser: _messages[index].role == 'user',
                              provider: _messages[index].provider,
                            ),
                      ),
              ),
              _Composer(
                controller: _input,
                search: _search,
                thinking: _thinking,
                execution: _execution,
                busy: _busy,
                onSearch: (v) => setState(() => _search = v),
                onThinking: (v) => setState(() => _thinking = v),
                onExecution: (v) => setState(() => _execution = v),
                attachments: _attachments,
                onRemoveAttachment: _removeAttachment,
                onAttach: _showAttachmentOptions,
                onSend: _send,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LogoMark extends StatelessWidget {
  const _LogoMark();

  @override
  Widget build(BuildContext context) => Container(
        width: 34,
        height: 34,
        decoration: BoxDecoration(color: const Color(0xFF3478F6), borderRadius: BorderRadius.circular(11)),
        child: const CustomPaint(painter: _CortexMarkPainter(), size: Size(24, 24)),
      );
}

class _CortexMarkPainter extends CustomPainter {
  const _CortexMarkPainter({this.light = true});
  final bool light;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 108, size.height / 108);
    final stroke = Paint()
      ..color = light ? Colors.white : const Color(0xFF3478F6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final mark = Path()..moveTo(20, 86)..lineTo(50, 18)..quadraticBezierTo(54, 10, 58, 18)..lineTo(88, 86);
    canvas.drawPath(mark, stroke);
    canvas.drawLine(const Offset(32, 64), const Offset(76, 64), stroke);
    final bolt = Paint()..color = light ? const Color(0xFF9FC2FF) : const Color(0xFF3478F6);
    final path = Path()..moveTo(60, 29)..lineTo(43, 57)..lineTo(56, 57)..lineTo(46, 79)..lineTo(70, 48)..lineTo(57, 48)..close();
    canvas.drawPath(path, bolt);
    canvas.restore();
  }
  @override
  bool shouldRepaint(covariant _CortexMarkPainter oldDelegate) => oldDelegate.light != light;
}

class _WelcomePanel extends StatelessWidget {
  const _WelcomePanel({required this.onPrompt});

  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 28),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 68,
              height: 68,
              decoration: BoxDecoration(
                color: const Color(0xFFEAF1FF),
                borderRadius: BorderRadius.circular(22),
              ),
              child: const CustomPaint(painter: _CortexMarkPainter(light: false), size: Size(44, 44)),
            ),
            const SizedBox(height: 20),
            const Text(
              'مرحباً بك في Alili Cortex',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 9),
            const Text(
              'مساحة واحدة لأفكارك وأسئلتك ومشاريعك.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Color(0xFF78869A),
                fontSize: 14,
                height: 1.7,
              ),
            ),
            const SizedBox(height: 26),
            _PromptCard(
              icon: Icons.code_rounded,
              title: 'أريد إنشاء تطبيق',
              subtitle: 'لنبدأ بتحويل فكرتك إلى مشروع.',
              onTap: () => onPrompt('أريد إنشاء تطبيق جديد.'),
            ),
            const SizedBox(height: 10),
            _PromptCard(
              icon: Icons.lightbulb_outline_rounded,
              title: 'لدي فكرة جديدة',
              subtitle: 'ساعدني على دراستها وتطويرها.',
              onTap: () => onPrompt('لدي فكرة أريد دراستها وتطويرها.'),
            ),
          ],
        ),
      ),
    );
  }
}

class _PromptCard extends StatelessWidget {
  const _PromptCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(15),
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFFE9EDF3)),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            children: [
              Icon(icon, color: const Color(0xFF3478F6), size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF7C899B),
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_left, color: Color(0xFF9AA5B5)),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatMessage {
  const _ChatMessage({required this.role, required this.content, this.provider});

  final String role;
  final String content;
  final String? provider;
}

class _PickedAttachment {
  const _PickedAttachment({
    required this.name,
    required this.path,
    required this.isImage,
  });

  final String name;
  final String? path;
  final bool isImage;
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.search,
    required this.thinking,
    required this.execution,
    required this.busy,
    required this.attachments,
    required this.onRemoveAttachment,
    required this.onSearch,
    required this.onThinking,
    required this.onExecution,
    required this.onAttach,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool search;
  final bool thinking;
  final bool execution;
  final bool busy;
  final List<_PickedAttachment> attachments;
  final ValueChanged<int> onRemoveAttachment;
  final ValueChanged<bool> onSearch;
  final ValueChanged<bool> onThinking;
  final ValueChanged<bool> onExecution;
  final VoidCallback onAttach;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(11, 9, 11, 12),
      decoration: const BoxDecoration(
        color: Color(0xFFF8FAFD),
        border: Border(top: BorderSide(color: Color(0xFFECEFF4))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Container(
              padding: const EdgeInsets.fromLTRB(7, 6, 12, 6),
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border.all(color: const Color(0xFFE2E8F0)),
                borderRadius: BorderRadius.circular(22),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (attachments.isNotEmpty) ...[
                    SizedBox(
                      height: 70,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: attachments.length,
                        separatorBuilder: (_, __) => const SizedBox(width: 8),
                        itemBuilder: (context, index) {
                          final attachment = attachments[index];
                          return Container(
                            width: 176,
                            padding: const EdgeInsets.symmetric(horizontal: 7),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF4F7FB),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              children: [
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(8),
                                  child: attachment.isImage && attachment.path != null
                                      ? Image.file(
                                          File(attachment.path!),
                                          width: 48,
                                          height: 48,
                                          fit: BoxFit.cover,
                                          errorBuilder: (_, __, ___) => const SizedBox(
                                            width: 48,
                                            height: 48,
                                            child: Icon(Icons.image_outlined),
                                          ),
                                        )
                                      : Container(
                                          width: 48,
                                          height: 48,
                                          color: const Color(0xFFE6EDF7),
                                          child: Icon(
                                            attachment.isImage
                                                ? Icons.image_outlined
                                                : Icons.insert_drive_file_outlined,
                                            color: const Color(0xFF60738D),
                                          ),
                                        ),
                                ),
                                const SizedBox(width: 7),
                                Expanded(
                                  child: Text(
                                    attachment.name,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(fontSize: 11),
                                  ),
                                ),
                                IconButton(
                                  tooltip: 'إزالة المرفق',
                                  onPressed: () => onRemoveAttachment(index),
                                  visualDensity: VisualDensity.compact,
                                  constraints: const BoxConstraints.tightFor(
                                    width: 28,
                                    height: 32,
                                  ),
                                  padding: EdgeInsets.zero,
                                  icon: const Icon(Icons.close, size: 17),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 5),
                  ],
                  TextField(
                    controller: controller,
                    minLines: 1,
                    maxLines: 3,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: const InputDecoration(
                      hintText: 'اكتب رسالتك هنا...',
                      hintStyle: TextStyle(
                        color: Color(0xFF9AA5B5),
                        fontSize: 14,
                      ),
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(vertical: 9),
                    ),
                  ),
                  Row(
                    children: [
                      IconButton(
                        tooltip: 'إضافة ملف',
                        onPressed: onAttach,
                        visualDensity: VisualDensity.compact,
                        constraints:
                            const BoxConstraints.tightFor(width: 34, height: 34),
                        icon: const Icon(Icons.add_rounded, size: 22),
                      ),
                      const Spacer(),
                      IconButton.filled(
                        tooltip: 'إرسال',
                        onPressed: busy ? null : onSend,
                        visualDensity: VisualDensity.compact,
                        constraints:
                            const BoxConstraints.tightFor(width: 36, height: 36),
                        icon: busy
                            ? const SizedBox(
                                width: 17,
                                height: 17,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.arrow_upward_rounded, size: 19),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _ModeToggle(
                icon: Icons.search_rounded,
                tooltip: 'البحث',
                selected: search,
                onPressed: () => onSearch(!search),
              ),
              const SizedBox(height: 7),
              _ModeToggle(
                icon: Icons.psychology_alt_outlined,
                tooltip: 'التفكير',
                selected: thinking,
                onPressed: () => onThinking(!thinking),
              ),
              const SizedBox(height: 7),
              _ModeToggle(
                icon: Icons.bolt_rounded,
                tooltip: 'التنفيذ',
                selected: execution,
                onPressed: () => onExecution(!execution),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ModeToggle extends StatelessWidget {
  const _ModeToggle({
    required this.icon,
    required this.tooltip,
    required this.selected,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final bool selected;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      style: IconButton.styleFrom(
        fixedSize: const Size(39, 39),
        padding: EdgeInsets.zero,
        backgroundColor:
            selected ? const Color(0xFF3478F6) : const Color(0xFFEAF0F8),
        foregroundColor:
            selected ? Colors.white : const Color(0xFF65758B),
      ),
      icon: Icon(icon, size: 20),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.text, required this.isUser, this.provider});

  final String text;
  final bool isUser;
  final String? provider;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: isUser ? AlignmentDirectional.centerStart : AlignmentDirectional.centerEnd,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 330),
        margin: const EdgeInsets.only(bottom: 13),
        padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFFEAF1FF) : Colors.white,
          border: isUser ? null : Border.all(color: const Color(0xFFE9EDF3)),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(text, style: const TextStyle(height: 1.55)),
            if (!isUser && provider != null) ...[
              const SizedBox(height: 7),
              Text(
                provider!,
                style: const TextStyle(fontSize: 10, color: Color(0xFF8793A4)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
