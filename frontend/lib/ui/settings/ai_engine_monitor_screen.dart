import 'package:flutter/material.dart';
import 'dart:async';
import '../../repositories/schedule_repository.dart';
import '../theme/app_theme.dart';

class AiEngineMonitorScreen extends StatefulWidget {
  final ScheduleRepository repository;

  const AiEngineMonitorScreen({super.key, required this.repository});

  @override
  State<AiEngineMonitorScreen> createState() => _AiEngineMonitorScreenState();
}

class _AiEngineMonitorScreenState extends State<AiEngineMonitorScreen> {
  Map<String, dynamic>? _status;
  Timer? _timer;
  final ScrollController _logController = ScrollController();

  final List<Map<String, dynamic>> _pipelineStages = [
    {
      "id": "MAPPING",
      "label": "Data Discovery",
      "icon": Icons.search_rounded,
      "desc": "Scanning namespaces and mapping entities"
    },
    {
      "id": "EXTRACTION",
      "label": "Feature Extraction",
      "icon": Icons.psychology_rounded,
      "desc": "Converting historical shifts to AI features"
    },
    {
      "id": "TRAINING",
      "label": "Neural Learning",
      "icon": Icons.model_training_rounded,
      "desc": "Stochastic Gradient Descent on global weights"
    },
    {
      "id": "IDLE",
      "label": "Inference Ready",
      "icon": Icons.check_circle_rounded,
      "desc": "Model deployed and serving affinity scores"
    },
  ];

  @override
  void initState() {
    super.initState();
    _fetchStatus();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      _fetchStatus();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _logController.dispose();
    super.dispose();
  }

  Future<void> _fetchStatus() async {
    try {
      final status = await widget.repository.getTrainingProgress();
      if (mounted) {
        setState(() {
          _status = status;
        });
        // Auto-scroll logs to bottom
        if (_logController.hasClients) {
          _logController.animateTo(
            _logController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
          );
        }
      }
    } catch (e) {
      print("Monitor error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    final currentPhase = _status?['phase'] ?? 'IDLE';
    final progress = (_status?['progress'] ?? 0.0) as double;
    final logs = (_status?['logs'] as List?)?.cast<String>() ?? [];

    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text("AI ENGINE LIVE MONITOR"),
        centerTitle: true,
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Row(
        children: [
          // Sidebar: Pipeline Steps
          Container(
            width: 320,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              border: Border(right: BorderSide(color: Colors.white.withOpacity(0.05))),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("NEURAL PIPELINE", style: TextStyle(color: AppTheme.textSecondary, fontWeight: FontWeight.w900, fontSize: 10, letterSpacing: 2)),
                const SizedBox(height: 32),
                Expanded(
                  child: ListView.separated(
                    itemCount: _pipelineStages.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 24),
                    itemBuilder: (context, index) {
                      final stage = _pipelineStages[index];
                      final isActive = stage['id'] == currentPhase;
                      final isComplete = _isStageComplete(stage['id'], currentPhase);

                      return _buildStageItem(stage, isActive, isComplete);
                    },
                  ),
                ),
                
                // Engine Health
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.03),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white10),
                  ),
                  child: Column(
                    children: [
                      _buildStatRow("Processed Samples", _status?['details']?['processed_samples']?.toString() ?? "0"),
                      const SizedBox(height: 8),
                      _buildStatRow("Current Loss", _status?['details']?['loss']?.toStringAsFixed(6) ?? "0.000000"),
                    ],
                  ),
                ),
              ],
            ),
          ),
          
          // Main Body: Progress & Logs
          Expanded(
            child: Column(
              children: [
                // Top: Main Status Card
                Container(
                  padding: const EdgeInsets.all(40),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(_status?['message'] ?? "Engine Starting...", style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w300)),
                                const SizedBox(height: 8),
                                Text("Phase: $currentPhase", style: TextStyle(color: AppTheme.aiGlow.withOpacity(0.7), fontWeight: FontWeight.bold, fontSize: 12, letterSpacing: 1.5)),
                              ],
                            ),
                          ),
                          Text("${(progress * 100).toInt()}%", style: const TextStyle(color: AppTheme.aiGlow, fontSize: 32, fontWeight: FontWeight.w900)),
                        ],
                      ),
                      const SizedBox(height: 24),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: LinearProgressIndicator(
                          value: progress,
                          minHeight: 12,
                          backgroundColor: Colors.white.withOpacity(0.05),
                          color: AppTheme.aiGlow,
                        ),
                      ),
                    ],
                  ),
                ),
                
                // Bottom: Console Logs
                Expanded(
                  child: Container(
                    margin: const EdgeInsets.fromLTRB(40, 0, 40, 40),
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(0.5),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.white10),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.terminal_rounded, color: Colors.blueAccent, size: 16),
                            const SizedBox(width: 8),
                            Text("ENGINE CONSOLE", style: TextStyle(color: Colors.blueAccent.withOpacity(0.8), fontWeight: FontWeight.bold, fontSize: 10, letterSpacing: 1.5)),
                            const Spacer(),
                            const CircleAvatar(radius: 4, backgroundColor: Colors.green),
                            const SizedBox(width: 8),
                            const Text("LIVE", style: TextStyle(color: Colors.green, fontSize: 8, fontWeight: FontWeight.bold)),
                          ],
                        ),
                        const Divider(height: 32, color: Colors.white10),
                        Expanded(
                          child: ListView.builder(
                            controller: _logController,
                            itemCount: logs.length,
                            itemBuilder: (context, index) {
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 4),
                                child: Text(
                                  logs[index],
                                  style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontFamily: "monospace"),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  bool _isStageComplete(String stageId, String currentPhase) {
    const list = ["MAPPING", "EXTRACTION", "TRAINING", "IDLE"];
    final currentIdx = list.indexOf(currentPhase);
    final stageIdx = list.indexOf(stageId);
    return stageIdx < currentIdx || currentPhase == "IDLE" && stageId != "IDLE";
  }

  Widget _buildStageItem(Map<String, dynamic> stage, bool isActive, bool isComplete) {
    final Color color = isActive ? AppTheme.aiGlow : (isComplete ? Colors.greenAccent : Colors.white24);
    
    return Row(
      children: [
        Icon(stage['icon'], color: color, size: 24),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(stage['label'], style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
              Text(stage['desc'], style: TextStyle(color: color.withOpacity(0.4), fontSize: 10)),
            ],
          ),
        ),
        if (isComplete) const Icon(Icons.check_circle, color: Colors.greenAccent, size: 14),
        if (isActive) const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.aiGlow)),
      ],
    );
  }

  Widget _buildStatRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold, fontFamily: "monospace")),
      ],
    );
  }
}
