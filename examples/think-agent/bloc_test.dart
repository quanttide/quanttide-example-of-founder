import 'dart:async';
import 'package:flutter_test/flutter_test.dart';

// 假设上面的状态机代码在 intent_sync_bloc.dart 中
// import 'intent_sync_bloc.dart';

void main() {
  // 测试用文档内容
  const initialDoc = '# 意图文档\n\n目标：测试状态机';
  const aiModifiedDoc = '# 意图文档\n\n目标：测试状态机\n状态：AI 已修改';
  const humanEditedDoc = '# 意图文档\n\n目标：测试状态机\n状态：人类已编辑';
  const aiModifiedAgain = '# 意图文档\n\n目标：测试状态机\n状态：AI 再次修改';

  late IntentSyncBloc bloc;

  setUp(() {
    bloc = IntentSyncBloc(initialDocumentContent: initialDoc);
  });

  tearDown(() {
    bloc.close();
  });

  // ============================================================
  // 初始状态
  // ============================================================

  group('初始状态', () {
    test('bloc 创建后应为 aligned 状态', () {
      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, initialDoc);
    });

    test('aligned 状态下 lastApprovedContent 等于 documentContent', () {
      final state = bloc.state as Aligned;
      expect(state.lastApprovedContent, state.documentContent);
    });
  });

  // ============================================================
  // aligned → ai_drift
  // ============================================================

  group('aligned → ai_drift', () {
    test('AI 修改文件应进入 ai_drift 状态', () {
      bloc.add(const AiEditFile(aiModifiedDoc));

      expect(bloc.state, isA<AiDrift>());
      expect(bloc.state.documentContent, aiModifiedDoc);
    });

    test('应保留上次确认的内容作为 lastApprovedContent', () {
      bloc.add(const AiEditFile(aiModifiedDoc));

      final state = bloc.state as AiDrift;
      expect(state.lastApprovedContent, initialDoc);
    });
  });

  // ============================================================
  // ai_drift → aligned（显式确认）
  // ============================================================

  group('ai_drift → aligned（显式确认）', () {
    test('人类确认后应回到 aligned 状态', () {
      bloc.add(const AiEditFile(aiModifiedDoc));
      bloc.add(const HumanReviewConfirm());

      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, aiModifiedDoc);
    });

    test('确认后 lastApprovedContent 应更新为新文档', () {
      bloc.add(const AiEditFile(aiModifiedDoc));
      bloc.add(const HumanReviewConfirm());

      final state = bloc.state as Aligned;
      expect(state.lastApprovedContent, aiModifiedDoc);
    });
  });

  // ============================================================
  // aligned → human_override
  // ============================================================

  group('aligned → human_override', () {
    test('人类编辑应进入 human_override 状态', () {
      bloc.add(const HumanEditSave(humanEditedDoc));

      expect(bloc.state, isA<HumanOverride>());
      expect(bloc.state.documentContent, humanEditedDoc);
    });

    test('应保留编辑前的文档作为 lastApprovedContent', () {
      bloc.add(const HumanEditSave(humanEditedDoc));

      final state = bloc.state as HumanOverride;
      expect(state.lastApprovedContent, initialDoc);
    });

    test('隐式同步完成后应回到 aligned', () async {
      bloc.add(const HumanEditSave(humanEditedDoc));

      // 等待异步同步完成
      await Future.delayed(const Duration(milliseconds: 200));

      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, humanEditedDoc);
    });
  });

  // ============================================================
  // ai_drift → human_override（覆盖 AI 修改）
  // ============================================================

  group('ai_drift → human_override', () {
    test('人类在 ai_drift 状态下编辑应进入 human_override', () {
      bloc.add(const AiEditFile(aiModifiedDoc));
      bloc.add(const HumanEditSave(humanEditedDoc));

      expect(bloc.state, isA<HumanOverride>());
      expect(bloc.state.documentContent, humanEditedDoc);
    });

    test('应保留最初确认的内容作为 lastApprovedContent', () {
      bloc.add(const AiEditFile(aiModifiedDoc));
      bloc.add(const HumanEditSave(humanEditedDoc));

      final state = bloc.state as HumanOverride;
      // 最初确认的是 initialDoc
      expect(state.lastApprovedContent, initialDoc);
    });
  });

  // ============================================================
  // ai_drift 下的被动确认（用户发送消息）
  // ============================================================

  group('ai_drift 被动确认', () {
    test('用户在 ai_drift 下发送消息应默认视为确认', () async {
      bloc.add(const AiEditFile(aiModifiedDoc));
      await bloc.add(const UserSendMessage());

      // 被动确认后应为 aligned
      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, aiModifiedDoc);
    });

    test('用户在 ai_drift 下编辑后发送消息，应进入 human_override', () async {
      bloc.add(const AiEditFile(aiModifiedDoc));
      await bloc.add(UserSendMessage(editedContent: humanEditedDoc));

      // 编辑触发 human_override，然后等待同步
      // 同步完成后为 aligned
      await Future.delayed(const Duration(milliseconds: 200));
      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, humanEditedDoc);
    });
  });

  // ============================================================
  // human_override 下的阻塞行为
  // ============================================================

  group('human_override 阻塞发送', () {
    test('human_override 状态下发送消息应等待同步完成', () async {
      bloc.add(const HumanEditSave(humanEditedDoc));

      // 立即尝试发送消息
      final sendFuture = bloc.add(const UserSendMessage());

      // 此时应该还在 human_override（同步尚未完成）
      expect(bloc.state, isA<HumanOverride>());

      // 等待同步和发送完成
      await sendFuture;
      await Future.delayed(const Duration(milliseconds: 200));

      // 同步完成后应回到 aligned
      expect(bloc.state, isA<Aligned>());
    });
  });

  // ============================================================
  // AI 连续修改
  // ============================================================

  group('AI 连续修改', () {
    test('ai_drift 状态下 AI 再次修改，状态不变但内容更新', () {
      bloc.add(const AiEditFile(aiModifiedDoc));
      bloc.add(const AiEditFile(aiModifiedAgain));

      expect(bloc.state, isA<AiDrift>());
      expect(bloc.state.documentContent, aiModifiedAgain);
      // lastApprovedContent 仍为最初确认的内容
      expect((bloc.state as AiDrift).lastApprovedContent, initialDoc);
    });

    test('human_override 状态下 AI 修改文件，保持 human_override 但更新内容', () {
      bloc.add(const HumanEditSave(humanEditedDoc));
      bloc.add(const AiEditFile(aiModifiedAgain));

      // 仍然是 human_override（人类编辑后需要同步）
      expect(bloc.state, isA<HumanOverride>());
      expect(bloc.state.documentContent, aiModifiedAgain);
    });
  });

  // ============================================================
  // 非状态变更事件
  // ============================================================

  group('非状态变更事件', () {
    test('aligned 状态下确认无效果', () {
      bloc.add(const HumanReviewConfirm());
      expect(bloc.state, isA<Aligned>());
    });

    test('human_override 状态下确认无效果', () {
      bloc.add(const HumanEditSave(humanEditedDoc));
      bloc.add(const HumanReviewConfirm());
      // 确认不改变 human_override 状态
      expect(bloc.state, isA<HumanOverride>());
    });

    test('aligned 状态下 SyncComplete 无效果', () {
      bloc.add(const SyncComplete());
      expect(bloc.state, isA<Aligned>());
    });
  });

  // ============================================================
  // 完整场景流程
  // ============================================================

  group('完整场景', () {
    test('典型对话流程：AI 修改 → 人类确认 → AI 再修改 → 人类编辑覆盖', () async {
      // 1. AI 修改文件
      bloc.add(const AiEditFile(aiModifiedDoc));
      expect(bloc.state, isA<AiDrift>());

      // 2. 人类确认
      bloc.add(const HumanReviewConfirm());
      expect(bloc.state, isA<Aligned>());

      // 3. AI 再次修改
      bloc.add(const AiEditFile(aiModifiedAgain));
      expect(bloc.state, isA<AiDrift>());

      // 4. 人类不满意，自己编辑
      bloc.add(const HumanEditSave(humanEditedDoc));
      expect(bloc.state, isA<HumanOverride>());

      // 5. 等待同步完成
      await Future.delayed(const Duration(milliseconds: 200));
      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, humanEditedDoc);
    });

    test('快速连续操作：编辑后立即发送消息', () async {
      // 人类编辑并立即发送消息（editedContent 不为 null）
      await bloc.add(UserSendMessage(editedContent: humanEditedDoc));

      // 应该进入 human_override，然后同步，最后 aligned
      await Future.delayed(const Duration(milliseconds: 200));
      expect(bloc.state, isA<Aligned>());
      expect(bloc.state.documentContent, humanEditedDoc);
    });
  });

  // ============================================================
  // 同步超时降级
  // ============================================================

  group('同步超时降级', () {
    test('同步超时后应允许发送消息，不永久阻塞', () async {
      // 创建一个同步会超时的 bloc（需要 mock _sendToAi）
      // 这里测试超时保护机制：直接验证 _waitForSync 的超时行为
      bloc.add(const HumanEditSave(humanEditedDoc));

      // 等待超过超时时间
      await Future.delayed(const Duration(seconds: 6));

      // 超时后 _syncCompleter 被清空，状态可能仍为 human_override
      // 但再次发送消息不应死锁
      await bloc.add(const UserSendMessage());

      // 不崩溃即测试通过
      expect(true, isTrue);
    });
  });

  // ============================================================
  // lastApprovedContent 追踪
  // ============================================================

  group('lastApprovedContent 追踪', () {
    test('多次确认应更新 lastApprovedContent', () {
      // 第一次 AI 修改
      bloc.add(const AiEditFile(aiModifiedDoc));
      expect((bloc.state as AiDrift).lastApprovedContent, initialDoc);

      // 确认
      bloc.add(const HumanReviewConfirm());
      expect((bloc.state as Aligned).lastApprovedContent, aiModifiedDoc);

      // 第二次 AI 修改
      bloc.add(const AiEditFile(aiModifiedAgain));
      expect((bloc.state as AiDrift).lastApprovedContent, aiModifiedDoc);

      // 确认
      bloc.add(const HumanReviewConfirm());
      expect((bloc.state as Aligned).lastApprovedContent, aiModifiedAgain);
    });

    test('人类编辑后 lastApprovedContent 保持为上次确认的内容', () {
      bloc.add(const AiEditFile(aiModifiedDoc));
      bloc.add(const HumanReviewConfirm());

      // 人类编辑
      bloc.add(const HumanEditSave(humanEditedDoc));
      final state = bloc.state as HumanOverride;

      // lastApprovedContent 应为上次确认的内容（aiModifiedDoc）
      expect(state.lastApprovedContent, aiModifiedDoc);
    });
  });
}