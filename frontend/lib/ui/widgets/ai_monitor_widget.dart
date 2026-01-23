import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:async';
import '../../repositories/schedule_repository.dart';
import '../theme/app_theme.dart';
import '../settings/ai_engine_monitor_screen.dart';

class AiMonitorWidget extends StatefulWidget {
  const AiMonitorWidget({super.key});

  @override
  State<AiMonitorWidget> createState() => _AiMonitorWidgetState();
}

class _AiMonitorWidgetState extends State<AiMonitorWidget> {
  Map<String, dynamic>? _status;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _fetchStatus();
    _timer = Timer.periodic(const Duration(seconds: 2), (timer) {
      _fetchStatus();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _fetchStatus() async {
    try {
      if (!mounted) return;
      final repo = context.read<ScheduleRepository>();
      final status = await repo.getTrainingProgress();
      if (mounted) {
        setState(() {
          _status = status;
        });
      }
    } catch (e) {
      debugPrint("AiMonitorWidget error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    final currentPhase = _status?['phase'] ?? 'IDLE';
    final progress = (_status?['progress'] ?? 0.0) as double;
    final message = _status?['message'] ?? 'Engine Standby';
    final logs = (_status?['logs'] as List?)?.cast<String>() ?? [];
    final isRunning = _status?['status'] == 'running';

    return Container(
      width: 300,
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.glassDecoration(opacity: 0.1),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Icon(Icons.psychology_rounded, color: AppTheme.aiGlow, size: 20),
              const SizedBox(width: 10),
              const Text("AI ENGINE LIVE", style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold, letterSpacing: 1)),
              const Spacer(),
              if (isRunning)
                const SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.aiGlow),
                )
              else
                const Icon(Icons.check_circle_rounded, color: Colors.greenAccent, size: 16),
            ],
          ),
          const Divider(height: 30, color: Colors.white10),
          
          Text(message, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
          const SizedBox(height: 12),
          
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 4,
              backgroundColor: Colors.white.withOpacity(0.05),
              color: AppTheme.aiGlow,
            ),
          ),
          
          const SizedBox(height: 16),
          _buildMiniStat("Phase", currentPhase),
          _buildMiniStat("Progress", "${(progress * 100).toInt()}%"),
          
          if (logs.isNotEmpty) ...[
            const SizedBox(height: 20),
            Container(
              height: 80,
              width: double.infinity,
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.3),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white10),
              ),
              child: ListView.builder(
                itemCount: logs.length > 5 ? 5 : logs.length,
                reverse: true,
                itemBuilder: (context, index) {
                  final log = logs[logs.length - 1 - index];
                  return Text(
                    log,
                    style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 8, fontFamily: "monospace"),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  );
                },
              ),
            ),
          ],
          
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              style: TextButton.styleFrom(
                backgroundColor: Colors.white.withOpacity(0.05),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => AiEngineMonitorScreen(
                    repository: context.read<ScheduleRepository>()
                  )),
                );
              },
              child: const Text("OPEN LIVE MONITOR", style: TextStyle(color: Colors.white70, fontSize: 10, fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMiniStat(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
          Text(value, style: const TextStyle(color: AppTheme.aiGlow, fontSize: 10, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
