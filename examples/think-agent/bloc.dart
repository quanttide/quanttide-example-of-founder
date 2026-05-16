import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';

// ============================================================
// 状态定义
// ============================================================

/// 意图版本一致性状态
/// 管理对象：AI 上下文中的意图文档与人类认可版本是否对齐
sealed class IntentSyncState {
  /// 当前意图文档内容（始终为最新文件内容）
  final String documentContent;

  /// 上次人类明确认可的文档内容（用于 ai_drift 状态下对比）
  final String? lastApprovedContent;

  const IntentSyncState({
    required this.documentContent,
    this.lastApprovedContent,
  });
}

/// 对齐：文件内容 = 人类认可版本，AI 已感知
class Aligned extends IntentSyncState {
  const Aligned({required super.documentContent})
      : super(lastApprovedContent: documentContent);
}

/// AI 漂移：AI 修改了文件，人类尚未确认
class AiDrift extends IntentSyncState {
  const AiDrift({
    required super.documentContent,
    required super.lastApprovedContent,
  });
}

/// 人类覆盖：人类手动编辑了文件，AI 尚未感知
class HumanOverride extends IntentSyncState {
  const HumanOverride({
    required super.documentContent,
    required super.lastApprovedContent,
  });
}

// ============================================================
// 事件定义
// ============================================================

sealed class IntentSyncEvent {
  const IntentSyncEvent();
}

/// AI 修改了意图文档文件（由文件监听触发）
class AiEditFile extends IntentSyncEvent {
  final String newContent;
  const AiEditFile(this.newContent);
}

/// 人类在右栏手动编辑并保存
class HumanEditSave extends IntentSyncEvent {
  final String newContent;
  const HumanEditSave(this.newContent);
}

/// 人类确认 AI 的修改（显式点击确认按钮，或被动由发送消息触发）
class HumanReviewConfirm extends IntentSyncEvent {
  const HumanReviewConfirm();
}

/// 隐式同步已完成
class SyncComplete extends IntentSyncEvent {
  const SyncComplete();
}

/// 用户准备发送新消息（需检查是否需要先同步）
class UserSendMessage extends IntentSyncEvent {
  /// 可选：如果用户同时编辑了文档，传入新内容
  final String? editedContent;
  const UserSendMessage({this.editedContent});
}

// ============================================================
// BLoC
// ============================================================

class IntentSyncBloc extends Bloc<IntentSyncEvent, IntentSyncState> {
  /// 用于在 human_override 状态下阻塞消息发送，等待同步完成
  Completer<void>? _syncCompleter;

  /// 是否正在执行隐式同步（防止重复同步）
  bool _isSyncing = false;

  IntentSyncBloc({required String initialDocumentContent})
      : super(Aligned(documentContent: initialDocumentContent));

  @override
  Stream<IntentSyncState> mapEventToState(IntentSyncEvent event) async* {
    switch (event) {
      // --------------------------------------------------
      // aligned → ai_drift
      // 规则：AI 每次修改文件都进入 ai_drift
      // 连续修改时只更新内容，不重复切状态
      // --------------------------------------------------
      case AiEditFile(:final newContent):
        yield switch (state) {
          Aligned() => AiDrift(
              documentContent: newContent,
              lastApprovedContent: state.documentContent,
            ),
          AiDrift() => AiDrift(
              documentContent: newContent,
              lastApprovedContent: state.lastApprovedContent,
            ),
          HumanOverride() => HumanOverride(
              documentContent: newContent,
              lastApprovedContent: state.lastApprovedContent,
            ),
        };

      // --------------------------------------------------
      // aligned / ai_drift → human_override
      // 规则：人类编辑优先，覆盖 AI 修改
      // --------------------------------------------------
      case HumanEditSave(:final newContent):
        final previousApproved = switch (state) {
          Aligned() => state.documentContent,
          AiDrift(:final lastApprovedContent) => lastApprovedContent,
          HumanOverride(:final lastApprovedContent) => lastApprovedContent,
        };
        yield HumanOverride(
          documentContent: newContent,
          lastApprovedContent: previousApproved,
        );
        // 启动隐式同步
        _startImplicitSync(newContent);

      // --------------------------------------------------
      // ai_drift → aligned（显式确认）
      // --------------------------------------------------
      case HumanReviewConfirm():
        if (state is AiDrift) {
          yield Aligned(documentContent: state.documentContent);
        }
        // 其他状态下的确认无效果

      // --------------------------------------------------
      // human_override → aligned
      // --------------------------------------------------
      case SyncComplete():
        if (state is HumanOverride) {
          yield Aligned(documentContent: state.documentContent);
          _isSyncing = false;
          _syncCompleter?.complete();
          _syncCompleter = null;
        }

      // --------------------------------------------------
      // 用户发送消息
      // 规则：
      // 1. 如果同时编辑了文档 → 先作为 HumanEditSave 处理
      // 2. ai_drift 且未编辑 → 默认视为确认（被动确认）
      // 3. human_override → 阻塞，等待同步完成
      // --------------------------------------------------
      case UserSendMessage(:final editedContent):
        // 情况1：用户在发送时编辑了文档
        if (editedContent != null) {
          add(HumanEditSave(editedContent));
          // 等待同步完成后再放行（见 _waitForSync）
          await _waitForSync();
          return;
        }

        // 情况2：ai_drift 下被动确认
        if (state is AiDrift) {
          add(const HumanReviewConfirm());
          // 确认后直接放行，不阻塞
          return;
        }

        // 情况3：human_override 下必须等待同步
        if (state is HumanOverride) {
          await _waitForSync();
          return;
        }

        // aligned 状态下直接放行
    }
  }

  // ============================================================
  // 隐式同步机制
  // ============================================================

  /// 启动隐式同步：将新文档内容注入 AI 上下文
  void _startImplicitSync(String content) {
    if (_isSyncing) return;
    _isSyncing = true;

    // 构造隐式系统消息
    final systemMessage = _buildSyncMessage(content);

    // 发送给 AI（不渲染到左栏）
    // TODO: 替换为实际的 Open Code API 调用
    _sendToAi(systemMessage).then((_) {
      add(const SyncComplete());
    }).catchError((error) {
      // 同步失败：降级为在下一轮用户消息中附加文档内容
      _isSyncing = false;
      _syncCompleter?.completeError(error);
      _syncCompleter = null;
    });
  }

  /// 构造同步消息
  String _buildSyncMessage(String content) {
    return '''
[SYSTEM] 意图文档已被用户手动更新，当前内容如下：
---
$content
---
请基于此意图文档继续对话。''';
  }

  /// 发送消息给 AI（占位，需接入 Open Code API）
  Future<void> _sendToAi(String message) async {
    // TODO: 调用 Open Code 接口注入系统消息
    // 消息不在 UI 中渲染，仅用于更新 AI 上下文
    await Future.delayed(const Duration(milliseconds: 100));
  }

  /// 等待隐式同步完成（带超时保护）
  Future<void> _waitForSync() async {
    if (_syncCompleter != null) return;

    _syncCompleter = Completer<void>();
    try {
      await _syncCompleter!.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () {
          // 超时降级：取消同步，允许发送（下轮消息中附带文档内容）
          _isSyncing = false;
          _syncCompleter = null;
        },
      );
    } catch (_) {
      // 同步失败，降级放行
    }
  }
}
