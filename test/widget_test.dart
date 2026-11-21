import 'package:alili_cortex/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders the Arabic Alili Cortex chat home', (tester) async {
    await tester.pumpWidget(const AliliCortexApp());

    expect(find.text('Alili Cortex'), findsOneWidget);
    expect(find.text('مرحباً بك في Alili Cortex'), findsOneWidget);
    expect(find.byTooltip('البحث'), findsOneWidget);
    expect(find.byTooltip('التفكير'), findsOneWidget);
    expect(find.byTooltip('التنفيذ'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
  });

  testWidgets('mode buttons toggle their selected state', (tester) async {
    await tester.pumpWidget(const AliliCortexApp());

    final searchButton = find.ancestor(
      of: find.byTooltip('البحث'),
      matching: find.byType(IconButton),
    );
    expect(searchButton, findsOneWidget);

    await tester.tap(find.byTooltip('البحث'));
    await tester.pump();

    final button = tester.widget<IconButton>(searchButton);
    expect(
      button.style?.backgroundColor?.resolve({}),
      const Color(0xFF3478F6),
    );
  });

  testWidgets('sends a typed message into the chat', (tester) async {
    await tester.pumpWidget(const AliliCortexApp());

    await tester.enterText(find.byType(TextField), 'اختبار الواجهة');
    await tester.tap(find.byTooltip('إرسال'));
    // Sending starts an asynchronous secure-storage/network flow. Pump one
    // frame only; pumpAndSettle would wait forever while the busy indicator animates.
    await tester.pump();

    expect(find.text('اختبار الواجهة'), findsOneWidget);
  });
  testWidgets('opens the attachment source chooser', (tester) async {
    await tester.pumpWidget(const AliliCortexApp());

    await tester.tap(find.byTooltip('إضافة ملف'));
    await tester.pumpAndSettle();

    expect(find.text('الصور'), findsOneWidget);
    expect(find.text('الملفات'), findsOneWidget);
  });

  testWidgets('starts a clean chat after tapping new chat', (tester) async {
    await tester.pumpWidget(const AliliCortexApp());

    await tester.enterText(find.byType(TextField), 'رسالة سابقة');
    await tester.tap(find.byTooltip('إرسال'));
    await tester.pump();

    expect(find.text('رسالة سابقة'), findsOneWidget);

    await tester.tap(find.byTooltip('محادثة جديدة'));
    await tester.pump();

    expect(find.text('رسالة سابقة'), findsNothing);
    expect(find.text('مرحباً بك في Alili Cortex'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
  });
}
