
import 'package:flutter/material.dart';
import '../../models/agent_models.dart';
import '../../repositories/schedule_repository.dart';
import '../../blocs/schedule_bloc.dart';
import '../theme/app_theme.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

class AiAdvisorDialog extends StatefulWidget {
  final List<Employment> employees;
  final List<Activity> activities;
  final DemandConfig currentConfig;
  final DateTime startDate;
  final DateTime endDate;

  const AiAdvisorDialog({
    super.key,
    required this.employees,
    required this.activities,
    required this.currentConfig,
    required this.startDate,
    required this.endDate,
  });

  @override
  State<AiAdvisorDialog> createState() => _AiAdvisorDialogState();
}

class _AiAdvisorDialogState extends State<AiAdvisorDialog> {
  bool _isLoading = true; // Stato di caricamento dell'analisi AI
  String _summary = ""; // Riassunto testuale fornito da Gemini
  List<dynamic> _suggestions = []; // Lista di suggerimenti azionabili
  String? _error; // Eventuali errori di rete o parsing
  final Map<int, bool> _applied = {}; // Tracciamento dei suggerimenti applicati localmente

  @override
  void initState() {
    super.initState();
    _fetchAnalysis();
  }

  Future<void> _fetchAnalysis() async {
    // Richiede l'analisi preventiva al backend inviando dipendenti, attività e configurazione attuale
    try {
      final repo = context.read<ScheduleRepository>();
      final result = await repo.getPreCheckAnalysis(
        employees: widget.employees,
        activities: widget.activities,
        config: widget.currentConfig.toJson(),
        startDate: widget.startDate,
        endDate: widget.endDate,
      );
      
      if (mounted) {
        setState(() {
          _summary = result['summary'] ?? "Analisi completata.";
          _suggestions = result['suggestions'] ?? [];
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
        width: 600,
        height: 500,
        decoration: AppTheme.glassDecoration(),
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(20),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Colors.white10)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.auto_awesome, color: AppTheme.aiGlow, size: 24),
                  const SizedBox(width: 12),
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("AI Generation Advisor",
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.bold)),
                      Text("Suggerimenti prima della generazione", style: TextStyle(color: Colors.white38, fontSize: 10)),
                    ],
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white54, size: 20),
                    onPressed: () => Navigator.pop(context, false),
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
                      ? Center(child: Text("Errore: $_error", style: const TextStyle(color: Colors.redAccent)))
                      : SingleChildScrollView(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(_summary, style: const TextStyle(color: Colors.white, fontSize: 14)),
                              const SizedBox(height: 20),
                              if (_suggestions.isEmpty)
                                const Center(
                                  child: Text("Nessun suggerimento particolare. La configurazione sembra ottimale.", 
                                    style: TextStyle(color: Colors.white38, fontSize: 12)),
                                ),
                              ..._suggestions.asMap().entries.map((entry) => _buildSuggestionCard(entry.key, entry.value)),
                            ],
                          ),
                        ),
            ),

            // Footer
            Container(
              padding: const EdgeInsets.all(20),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: Colors.white10)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text("PROSEGUI SENZA MODIFICHE", style: TextStyle(color: Colors.white54, fontSize: 12)),
                  ),
                  const SizedBox(width: 16),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                    ),
                    onPressed: () => Navigator.pop(context, true), // true means Proceed to generation
                    child: const Text("AVVIA GENERAZIONE", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionCard(int index, Map<String, dynamic> suggestion) {
    final isApplied = _applied[index] ?? false;
    final type = suggestion['type'] ?? 'info';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.aiGlow.withOpacity(0.05),
        border: Border.all(color: isApplied ? Colors.greenAccent.withOpacity(0.5) : AppTheme.aiGlow.withOpacity(0.2)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(suggestion['title'] ?? "Suggerimento", 
                style: const TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold, fontSize: 14)),
              const Spacer(),
              if (type == 'update_config')
                TextButton.icon(
                  onPressed: isApplied ? null : () async {
                    final payload = suggestion['payload'] as Map<String, dynamic>?;
                    if (payload != null) {
                      final repo = context.read<ScheduleRepository>();
                      final bloc = context.read<ScheduleBloc>();

                      // 1. Fetch current config from server for safe patching
                      final currentServerConfig = await repo.getAlgorithmConfig();
                      
                      // 2. Patch with suggestion
                      final updatedConfig = {
                        ...currentServerConfig,
                        ...payload
                      };

                      // 3. Save to backend (PERSISTENCE FIX)
                      await repo.saveAlgorithmConfig(updatedConfig);

                      // 4. Update Bloc to reflect change in UI
                      final demandConfig = DemandConfig.fromJson(updatedConfig);
                      bloc.add(UpdateDemandConfig(demandConfig));
                    }
                    
                    if (mounted) {
                      setState(() => _applied[index] = true);
                    }
                  },
                  icon: Icon(isApplied ? Icons.check_circle : Icons.add_circle_outline, 
                    color: isApplied ? Colors.greenAccent : Colors.white70, size: 16),
                  label: Text(isApplied ? "APPLICATO" : "APPLICA", 
                    style: TextStyle(color: isApplied ? Colors.greenAccent : Colors.white70, fontSize: 11, fontWeight: FontWeight.bold)),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(suggestion['description'] ?? "", style: const TextStyle(color: Colors.white70, fontSize: 12)),
        ],
      ),
    );
  }
}
