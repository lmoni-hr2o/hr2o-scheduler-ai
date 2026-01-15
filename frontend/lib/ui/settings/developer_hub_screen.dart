import 'package:flutter/material.dart';
import '../../repositories/schedule_repository.dart';

class DeveloperHubScreen extends StatefulWidget {
  final ScheduleRepository repository;

  const DeveloperHubScreen({super.key, required this.repository});

  @override
  State<DeveloperHubScreen> createState() => _DeveloperHubScreenState();
}

class _DeveloperHubScreenState extends State<DeveloperHubScreen> {
  Map<String, dynamic>? _stats;
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
      setState(() {
        _stats = stats;
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
          _buildSectionHeader('Model Status: ${_stats!['status']?.toUpperCase()}'),
          const SizedBox(height: 16),
          _buildStatCard(
            'Neural Architecture',
            Icons.account_tree,
            Column(
              children: architecture.map((layer) {
                return ListTile(
                  dense: true,
                  title: Text('Layer ${layer['layer']}: ${layer['name']}'),
                  subtitle: Text('Units: ${layer['units']}'),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 16),
          _buildStatCard(
            'Synaptic Weights',
            Icons.hub,
            Column(
              children: [
                _buildStatRow('Total Parameters', weights['count']?.toString() ?? '0'),
                _buildStatRow('Mean Weight', weights['mean']?.toStringAsFixed(4) ?? '0'),
                _buildStatRow('Std Deviation', weights['std']?.toStringAsFixed(4) ?? '0'),
                _buildStatRow('Min / Max', '${weights['min']?.toStringAsFixed(2)} / ${weights['max']?.toStringAsFixed(2)}'),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _buildStatCard(
            'GCS Storage',
            Icons.cloud_done,
            Column(
              children: [
                _buildStatRow('Bucket', _stats!['bucket'] ?? 'N/A'),
                _buildStatRow('Weights File', _stats!['filename'] ?? 'N/A'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).primaryColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Theme.of(context).primaryColor.withOpacity(0.3)),
      ),
      child: Text(
        title,
        style: TextStyle(
          fontWeight: FontWeight.bold,
          color: Theme.of(context).primaryColor,
        ),
      ),
    );
  }

  Widget _buildStatCard(String title, IconData icon, Widget content) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: Colors.blue),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
              ],
            ),
            const Divider(),
            content,
          ],
        ),
      ),
    );
  }

  Widget _buildStatRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey.shade600)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontFamily: 'monospace')),
        ],
      ),
    );
  }
}
