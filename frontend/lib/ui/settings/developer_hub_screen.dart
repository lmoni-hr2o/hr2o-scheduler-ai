import 'package:flutter/material.dart';
import '../../repositories/schedule_repository.dart';
import 'data_mapping_screen.dart';

class DeveloperHubScreen extends StatefulWidget {
  final ScheduleRepository repository;

  const DeveloperHubScreen({super.key, required this.repository});

  @override
  State<DeveloperHubScreen> createState() => _DeveloperHubScreenState();
}

class _DeveloperHubScreenState extends State<DeveloperHubScreen> {
  Map<String, dynamic>? _stats;
  Map<String, double> _localConfig = {};
  List<dynamic> _currentActivities = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadStats();
  }

  Future<void> _loadStats() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final stats = await widget.repository.getModelStats();
      final config = await widget.repository.getAlgorithmConfig();
      final activities = await widget.repository.getActivities();
      setState(() {
        _stats = stats;
        _currentActivities = activities;
        _localConfig = {
          'affinity_weight': config['affinity_weight']?.toDouble() ?? 1.0,
          'penalty_unassigned': config['penalty_unassigned']?.toDouble() ?? 100.0,
          'max_hours_weekly': config['max_hours_weekly']?.toDouble() ?? 40.0,
        };
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Developer Hub'),
        actions: [
          IconButton(
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => DataMappingScreen(repository: widget.repository),
                ),
              );
            },
            icon: const Icon(Icons.link, color: Colors.greenAccent),
            tooltip: 'Data Association Mappings',
          ),
          IconButton(
            onPressed: () async {
              await widget.repository.retrain();
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("Global Retraining Started!")),
                );
                _loadStats();
              }
            },
            icon: const Icon(Icons.psychology, color: Colors.blueAccent),
            tooltip: 'Retrain Global Model',
          ),
          IconButton(
            onPressed: () async {
              await widget.repository.resetStatus();
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("System status reset to IDLE")),
                );
                _loadStats();
              }
            },
            icon: const Icon(Icons.flash_on, color: Colors.orangeAccent),
            tooltip: 'Force Reset AI Status',
          ),
          IconButton(
            onPressed: _loadStats,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error'))
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    if (_stats == null) return const Center(child: Text('No data'));

    final architecture = _stats!['architecture'] as List<dynamic>? ?? [];
    final weights = _stats!['weights_stats'] as Map<String, dynamic>? ?? {};

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Engine Brain Status: ${_stats!['status']?.toUpperCase()}'),
          if (_stats!['status'] == 'disabled' || _stats!['status'] == 'error')
            Padding(
              padding: const EdgeInsets.only(top: 8.0),
              child: Text(
                "⚠️ ERROR: ${_stats!['error'] ?? _stats!['message'] ?? 'Unknown error'}",
                style: const TextStyle(color: Colors.redAccent, fontSize: 12, fontWeight: FontWeight.bold),
              ),
            ),
          const SizedBox(height: 16),
          
          // Neural Performance Card (Live)
          FutureBuilder<Map<String, dynamic>>(
            future: widget.repository.getTrainingProgress(),
            builder: (context, snapshot) {
              final progress = snapshot.data;
              final details = progress?['details'] as Map<String, dynamic>? ?? {};
              return _buildStatCard(
                'Neural Performance',
                Icons.insights_rounded,
                Column(
                  children: [
                    _buildStatRow('Current Phase', progress?['phase'] ?? 'IDLE'),
                    _buildStatRow('Estimated Accuracy', '${((details['accuracy'] ?? 0.0) * 100).toStringAsFixed(1)}%'),
                    _buildStatRow('Training Loss', (details['loss'] ?? 0.0).toStringAsFixed(6)),
                    _buildStatRow('Dataset Size', '${details['dataset_size'] ?? 0} samples'),
                    _buildStatRow('Last Brain Update', details['last_run'] ?? 'N/A'),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: (progress?['progress'] ?? 0.0).toDouble(),
                        minHeight: 8,
                        color: Colors.blue,
                        backgroundColor: Colors.blue.withOpacity(0.1),
                      ),
                    ),
                  ],
                ),
              );
            }
          ),
          const SizedBox(height: 16),

          // Data Ingestion Health Card (Diagnostics)
          FutureBuilder<Map<String, dynamic>>(
            future: widget.repository.getDiagnostics(),
            builder: (context, snapshot) {
              final diag = snapshot.data ?? {};
              final double score = (diag['quality_score'] ?? 0.0).toDouble();
              
              return _buildStatCard(
                'Data Ingestion Health',
                Icons.health_and_safety_rounded,
                Column(
                  children: [
                    _buildStatRow('Data Quality Score', '${score.toStringAsFixed(1)}%'),
                    const SizedBox(height: 10),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(5),
                      child: LinearProgressIndicator(
                        value: score / 100,
                        minHeight: 12,
                        color: score > 70 ? Colors.green : (score > 40 ? Colors.orange : Colors.red),
                        backgroundColor: Colors.grey.withOpacity(0.1),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildStatRow('Total Employees', '${diag['total_employees'] ?? 0}'),
                    _buildStatRow(' - with full address', '${diag['employees_with_address'] ?? 0}'),
                    _buildStatRow(' - with birth date', '${diag['employees_with_born_date'] ?? 0}'),
                    const Divider(height: 24),
                    _buildStatRow('Total Activities', '${diag['total_activities'] ?? 0}'),
                    _buildStatRow(' - with location', '${diag['activities_with_address'] ?? 0}'),
                    _buildStatRow('Historical Records', '${diag['total_periods'] ?? 0}'),
                    if (score < 50) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(color: Colors.red.withOpacity(0.05), borderRadius: BorderRadius.circular(8)),
                        child: const Text(
                          "⚠️ ATTENZIONE: La mancanza di indirizzi o storico impedisce all'IA di calcolare l'affinità correttamente.",
                          style: TextStyle(color: Colors.red, fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ],
                ),
              );
            }
          ),
          const SizedBox(height: 16),

          // Neural Demand Map (MIA Thinking Draft)
          FutureBuilder<Map<String, dynamic>>(
            future: widget.repository.learnDemand(),
            builder: (context, snapshot) {
              final data = snapshot.data?['profile'] as Map<String, dynamic>? ?? {};
              
              if (data.isEmpty) return const SizedBox.shrink();

              return _buildStatCard(
                'Neural Demand Model (MIA Draft)',
                Icons.psychology_alt_rounded,
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      "Pattern di turnazione appresi dallo storico per questa azienda:",
                      style: TextStyle(color: Colors.grey, fontSize: 11),
                    ),
                    const SizedBox(height: 12),
                    ...data.entries.map((entry) {
                      final actId = entry.key;
                      final dows = entry.value as Map<String, dynamic>;
                      final actName = _currentActivities.where((a) => a.id == actId).firstOrNull?.name ?? "ID: $actId";

                      return Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.03),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: Colors.white.withOpacity(0.05)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(actName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.blueAccent)),
                            const SizedBox(height: 6),
                            for (var dow in dows.keys.toList()..sort()) ...[
                              _buildDemandRow(dow, dows[dow]),
                            ],
                          ],
                        ),
                      );
                    }).toList(),
                  ],
                ),
              );
            }
          ),
          const SizedBox(height: 16),

          _buildStatCard(
            'Neural Architecture',
            Icons.account_tree_rounded,
            architecture.isEmpty 
              ? const Padding(
                  padding: EdgeInsets.all(8.0),
                  child: Text("Componente neurale non rilevato o in caricamento...", style: TextStyle(color: Colors.grey, fontSize: 12)),
                )
              : Column(
                  children: architecture.map((layer) {
                    return ListTile(
                      dense: true,
                      title: Text('Layer ${layer['layer'] ?? '?'}: ${layer['name'] ?? 'Unknown'}'),
                      subtitle: Text('Units: ${layer['units'] ?? 'N/A'}'),
                    );
                  }).toList(),
                ),
          ),
          const SizedBox(height: 16),

          _buildStatCard(
            'Synaptic Weights',
            Icons.hub_rounded,
            Column(
              children: [
                _buildStatRow('Total Parameters', weights['count']?.toString() ?? '0'),
                _buildStatRow('Mean Weight', weights['mean']?.toStringAsFixed(4) ?? '0.0000'),
                _buildStatRow('Std Deviation', weights['std']?.toStringAsFixed(4) ?? '0.0000'),
                _buildStatRow('Min / Max', '${weights['min']?.toStringAsFixed(2) ?? '0.00'} / ${weights['max']?.toStringAsFixed(2) ?? '0.00'}'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          _buildStatCard(
            'GCS Storage',
            Icons.cloud_done_rounded,
            Column(
              children: [
                _buildStatRow('Bucket', _stats!['bucket']?.toString() ?? 'N/A'),
                _buildStatRow('Weights File', _stats!['filename']?.toString() ?? 'N/A'),
              ],
            ),
          ),
          const SizedBox(height: 16),

          _buildStatCard(
            'Synaptic Controls (AI Tuning)',
            Icons.settings_input_component_rounded,
            Column(
              children: [
                _buildConfigSlider(
                  'affinity_weight',
                  'AI Affinity Weight', 
                  'How much to trust AI predictions',
                  _localConfig['affinity_weight'] ?? 1.0,
                  (val) => widget.repository.saveAlgorithmConfig({'affinity_weight': val}),
                ),
                _buildConfigSlider(
                  'penalty_unassigned',
                  'Unassigned Penalty', 
                  'Punishment for empty shifts',
                  _localConfig['penalty_unassigned'] ?? 100.0,
                  (val) => widget.repository.saveAlgorithmConfig({'penalty_unassigned': val}),
                  min: 0, max: 1000,
                ),
                _buildConfigSlider(
                  'max_hours_weekly',
                  'Max Weekly Hours', 
                  'Labor law limit',
                  _localConfig['max_hours_weekly'] ?? 40.0,
                  (val) => widget.repository.saveAlgorithmConfig({'max_hours_weekly': val}),
                  min: 0, max: 60,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfigSlider(String key, String label, String sub, double val, Function(double) onSave, {double min=0, double max=2}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.blue.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  max > 10 ? val.toInt().toString() : val.toStringAsFixed(2),
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.blue, fontFamily: 'monospace'),
                ),
              ),
            ],
          ),
          Text(sub, style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
          const SizedBox(height: 8),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: Colors.blue,
              inactiveTrackColor: Colors.blue.withOpacity(0.1),
              thumbColor: Colors.blue,
              overlayColor: Colors.blue.withOpacity(0.1),
            ),
            child: Slider(
              value: val,
              min: min,
              max: max,
              divisions: max > 10 ? max.toInt() : 100,
              onChanged: (newVal) {
                setState(() {
                  _localConfig[key] = newVal;
                });
              },
              onChangeEnd: (newVal) async {
                await onSave(newVal);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text("$label salvato: ${max > 10 ? newVal.toInt() : newVal.toStringAsFixed(2)}")),
                  );
                }
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.blue.withOpacity(0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.blue.withOpacity(0.1)),
      ),
      child: Text(
        title,
        style: const TextStyle(
          fontWeight: FontWeight.w900,
          color: Colors.blue,
          letterSpacing: 1,
        ),
      ),
    );
  }

  Widget _buildStatCard(String title, IconData icon, Widget content) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.grey.shade100),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.02), blurRadius: 10, offset: const Offset(0, 4)),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: Colors.blue, size: 22),
                const SizedBox(width: 12),
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16, letterSpacing: 0.5),
                ),
              ],
            ),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 15),
              child: Divider(height: 1),
            ),
            content,
          ],
        ),
      ),
    );
  }

  Widget _buildDemandRow(String dow, dynamic slots) {
    final days = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
    final dowIdx = int.tryParse(dow) ?? 0;
    final dayName = dowIdx >= 0 && dowIdx < 7 ? days[dowIdx] : dow;
    
    final List listSlots = slots is List ? slots : [slots];

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 35, child: Text(dayName, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white54))),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: listSlots.map((s) {
                return Text(
                  "${s['start_time']} - ${s['end_time']} (${s['quantity']}x)",
                  style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontFamily: 'monospace', fontSize: 13)),
        ],
      ),
    );
  }
}
