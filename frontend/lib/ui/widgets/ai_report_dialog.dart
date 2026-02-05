
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../../repositories/schedule_repository.dart';
import '../theme/app_theme.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../models/agent_models.dart';
import '../../blocs/schedule_bloc.dart';

class AiReportDialog extends StatefulWidget {
  final List<dynamic> schedule;
  final DateTime startDate;
  final DateTime endDate;

  const AiReportDialog({
    super.key, 
    required this.schedule,
    required this.startDate,
    required this.endDate,
  });

  @override
  State<AiReportDialog> createState() => _AiReportDialogState();
}

class _AiReportDialogState extends State<AiReportDialog> {
  bool _isLoading = true;
  Map<String, dynamic>? _report;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchAnalysis();
  }

  Future<void> _fetchAnalysis() async {
    try {
      final repo = context.read<ScheduleRepository>();
      final result = await repo.getAiAnalysis(widget.schedule);
      if (mounted) {
        setState(() {
          _report = result;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.all(24),
      child: Container(
        width: 800,
        height: 700,
        decoration: AppTheme.glassDecoration(),
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(24),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Colors.white10)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.psychology, color: AppTheme.aiGlow, size: 28),
                  const SizedBox(width: 16),
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("AI Analysis Report",
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.bold)),
                      Text("Analisi Economica e Tecnica", style: TextStyle(color: Colors.white38, fontSize: 11)),
                    ],
                  ),
                  const Spacer(),
                  // LEARNING BUTTON
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.greenAccent.withOpacity(0.1),
                      side: const BorderSide(color: Colors.greenAccent),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    icon: const Icon(Icons.model_training, color: Colors.greenAccent, size: 16),
                    label: const Text("SALVA COME ESEMPIO", style: TextStyle(color: Colors.greenAccent, fontSize: 12, fontWeight: FontWeight.bold)),
                    onPressed: () async {
                       final repo = context.read<ScheduleRepository>();
                       await repo.submitScheduleFeedback(widget.schedule);
                       if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text("L'IA ha imparato da questo scenario!"))
                          );
                       }
                    },
                  ),
                  const SizedBox(width: 12),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white54),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),

            // Content
            Expanded(
              child: _isLoading
                  ? const Center(
                      child: CircularProgressIndicator(color: AppTheme.aiGlow))
                  : _error != null
                      ? Center(
                          child: Text("Error: $_error",
                              style: const TextStyle(color: Colors.redAccent)))
                      : SingleChildScrollView(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Summary Section
                              _buildSectionHeader("EXECUTIVE SUMMARY", Icons.summarize),
                              const SizedBox(height: 12),
                              Text(
                                _report?['summary'] ?? "No summary available.",
                                style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.5),
                              ),
                              const SizedBox(height: 32),

                              // Risks Section
                              _buildSectionHeader("RISK ASSESSMENT", Icons.warning_amber_rounded, color: Colors.orangeAccent),
                              const SizedBox(height: 12),
                              ...(_report?['risks'] as List? ?? []).map((r) => _buildRiskCard(r)),

                              const SizedBox(height: 32),

                              // Actions Section
                              _buildSectionHeader("RECOMMENDED ACTIONS", Icons.bolt, color: AppTheme.accent),
                              const SizedBox(height: 12),
                              ...(_report?['actions'] as List? ?? []).map((a) => _buildActionCard(a)),
                            ],
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon, {Color color = AppTheme.aiGlow}) {
    return Row(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(width: 8),
        Text(title, style: TextStyle(color: color, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
      ],
    );
  }

  Widget _buildRiskCard(Map<String, dynamic> risk) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.orangeAccent.withOpacity(0.1),
        border: Border.all(color: Colors.orangeAccent.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(risk['title'] ?? "Unknown Risk", 
                style: const TextStyle(color: Colors.orangeAccent, fontWeight: FontWeight.bold, fontSize: 16)),
              const Spacer(),
              _buildTag(risk['severity'] ?? 'MED', Colors.orange),
            ],
          ),
          const SizedBox(height: 8),
          Text(risk['description'] ?? risk['reason'] ?? "", 
            style: const TextStyle(color: Colors.white60)),
        ],
      ),
    );
  }

  Widget _buildActionCard(Map<String, dynamic> action) {
    final type = action['type'] ?? 'info';
    final payload = action['payload'] as Map<String, dynamic>?;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.accent.withOpacity(0.1),
        border: Border.all(color: AppTheme.accent.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
               const Icon(Icons.check_circle_outline, color: AppTheme.accent),
               const SizedBox(width: 16),
               Expanded(
                 child: Column(
                   crossAxisAlignment: CrossAxisAlignment.start,
                   children: [
                     Text(action['title'] ?? "Action", 
                       style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                     if (action['description'] != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: Text(action['description'], style: const TextStyle(color: Colors.white54, fontSize: 13)),
                        ),
                   ],
                 ),
               ),
               _buildTag(action['priority'] ?? 'HIGH', AppTheme.accent),
            ],
          ),
          if (type == 'update_config' && payload != null) ...[
             const SizedBox(height: 16),
             Row(
               mainAxisAlignment: MainAxisAlignment.end,
               children: [
                 TextButton.icon(
                   style: TextButton.styleFrom(
                     foregroundColor: AppTheme.aiGlow,
                     padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                     backgroundColor: AppTheme.aiGlow.withOpacity(0.1),
                   ),
                   icon: const Icon(Icons.flash_on, size: 16),
                   label: const Text("APPLICA PREFERENZA", style: TextStyle(fontWeight: FontWeight.bold)),
                   onPressed: () async {
                      try {
                        final repo = context.read<ScheduleRepository>();
                        final bloc = context.read<ScheduleBloc>();
                        
                        // 1. Fetch current config
                        Map<String, dynamic> config = await repo.getAlgorithmConfig();
                        // 2. Patch with payload
                        config.addAll(payload);
                        // 3. Save to repository
                        await repo.saveAlgorithmConfig(config);
                        
                        // 4. Update Bloc's internal demand config
                        final demandConfig = DemandConfig.fromJson(config);
                        bloc.add(UpdateDemandConfig(demandConfig));
                        
                        // 5. TRIGGER IMMEDIATE GENERATION
                        bloc.add(GenerateSchedules(widget.startDate, widget.endDate));
                        
                        if (mounted) {
                          Navigator.pop(context); // Close report to show generation progress
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text("Preferenza applicata. Rigenerazione in corso..."),
                              backgroundColor: AppTheme.aiGlow,
                            )
                          );
                        }
                      } catch (e) {
                         if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Errore: $e")));
                         }
                      }
                   },
                 ),
               ],
             ),
          ]
        ],
      ),
    );
  }

  Widget _buildTag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(text.toUpperCase(), style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
    );
  }
}
