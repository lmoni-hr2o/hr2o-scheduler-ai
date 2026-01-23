import 'package:flutter/material.dart';
import 'dart:convert';
import '../../repositories/schedule_repository.dart';

class DataMappingScreen extends StatefulWidget {
  final ScheduleRepository repository;

  const DataMappingScreen({super.key, required this.repository});

  @override
  State<DataMappingScreen> createState() => _DataMappingScreenState();
}

class _DataMappingScreenState extends State<DataMappingScreen> {
  bool _loading = true;
  String? _error;
  
  Map<String, List<String>> _schema = {};
  List<Map<String, dynamic>> _features = [];
  Map<String, List<String>> _currentMappings = {};

  bool _hasChanges = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final schema = await widget.repository.getSchema();
      final features = await widget.repository.getFeatures();
      final mappings = await widget.repository.getMappings();

      setState(() {
        _schema = schema;
        _features = features;
        _currentMappings = mappings;
        _hasChanges = false;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _saveChanges() async {
    setState(() => _loading = true);
    try {
      await widget.repository.saveMappings(_currentMappings);
      setState(() {
        _hasChanges = false;
        _loading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Mappings saved successfully!')),
        );
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _addMapping(String featureId, String fieldPath) {
    setState(() {
      if (!_currentMappings.containsKey(featureId)) {
        _currentMappings[featureId] = [];
      }
      if (!_currentMappings[featureId]!.contains(fieldPath)) {
        _currentMappings[featureId]!.add(fieldPath);
        _hasChanges = true;
      }
    });
  }

  void _removeMapping(String featureId, String fieldPath) {
    setState(() {
      _currentMappings[featureId]?.remove(fieldPath);
      _hasChanges = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Data Association'),
        actions: [
          if (_hasChanges)
            TextButton.icon(
              onPressed: _saveChanges,
              icon: const Icon(Icons.save, color: Colors.white),
              label: const Text('Save Changes', style: TextStyle(color: Colors.white)),
              style: TextButton.styleFrom(backgroundColor: Colors.blue),
            ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: () {
              if (_hasChanges) {
                showDialog(
                  context: context,
                  builder: (c) => AlertDialog(
                    title: const Text("Discard Changes?"),
                    content: const Text("You have unsaved changes. Are you sure you want to refresh?"),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(c), child: const Text("Cancel")),
                      TextButton(onPressed: () {
                        Navigator.pop(c);
                        _loadData();
                      }, child: const Text("Discard & Refresh", style: TextStyle(color: Colors.red))),
                    ],
                  ),
                );
              } else {
                _loadData();
              }
            },
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
    return Row(
      children: [
        // Left Panel: Available Schema Fields
        Expanded(
          flex: 1,
          child: _buildSchemaPanel(),
        ),
        
        const VerticalDivider(width: 1),
        
        // Right Panel: Model Features & Mappings
        Expanded(
          flex: 2,
          child: _buildFeaturesPanel(),
        ),
      ],
    );
  }

  Widget _buildSchemaPanel() {
    return Container(
      color: Colors.grey.shade50,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPanelHeader('Available Raw Fields', Icons.data_array),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _buildSchemaSection('Employment', _schema['Employment'] ?? []),
                _buildSchemaSection('Activity', _schema['Activity'] ?? []),
                _buildSchemaSection('Period', _schema['Period'] ?? []),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSchemaSection(String title, List<String> fields) {
    if (fields.isEmpty) return const SizedBox.shrink();
    return ExpansionTile(
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.black87)),
      subtitle: Text('${fields.length} detected fields', style: const TextStyle(fontSize: 12, color: Colors.black54)),
      children: fields.map((f) => ListTile(
        dense: true,
        title: Text(f, style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: Colors.black87)),
        trailing: const Icon(Icons.copy, size: 14, color: Colors.grey),
        onTap: () {
          // Allow copying to clipboard or dragging
          ScaffoldMessenger.of(context).showSnackBar(
             SnackBar(content: Text('Field "$f" copied (use "Add Relationship" on the right)')),
          );
        },
      )).toList(),
    );
  }

  Widget _buildFeaturesPanel() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildPanelHeader('AI Model Requirements & Association', Icons.psychology),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: _features.length,
            itemBuilder: (context, index) {
              final feature = _features[index];
              final featureId = feature['id'];
              final associatedFields = _currentMappings[featureId] ?? [];
              
              return _buildFeatureCard(feature, associatedFields);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildFeatureCard(Map<String, dynamic> feature, List<String> associates) {
    final featureId = feature['id'];
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.02), blurRadius: 4, offset: const Offset(0, 2)),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  feature['name'] ?? '',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                _buildStatusChip(associates.isNotEmpty),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              feature['description'] ?? '',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
            ),
            const SizedBox(height: 12),
            const Text(
              'Associated Input Paths:',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.blue),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: associates.isEmpty
                  ? [
                      const Text(
                        'No direct path mapped. Using defaults.',
                        style: TextStyle(color: Colors.orange, fontSize: 11, fontStyle: FontStyle.italic),
                      )
                    ]
                  : associates.map((a) => Chip(
                      label: Text(a, style: const TextStyle(fontSize: 10, fontFamily: 'monospace')),
                      backgroundColor: Colors.blue.withOpacity(0.05),
                      labelPadding: const EdgeInsets.symmetric(horizontal: 4),
                      visualDensity: VisualDensity.compact,
                      onDeleted: () => _removeMapping(featureId, a),
                    )).toList(),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => _showFieldSelector(featureId),
              icon: const Icon(Icons.add_link, size: 14),
              label: const Text('Add Data Source', style: TextStyle(fontSize: 12)),
              style: OutlinedButton.styleFrom(visualDensity: VisualDensity.compact),
            ),
          ],
        ),
      ),
    );
  }

  void _showFieldSelector(String featureId) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text("Select Data Source for '$featureId'"),
        content: SizedBox(
          width: 400,
          height: 500,
          child: ListView(
            children: _schema.entries.map((entry) {
              return ExpansionTile(
                title: Text(entry.key, style: const TextStyle(fontWeight: FontWeight.bold)),
                initiallyExpanded: true,
                children: entry.value.map((field) {
                  final isSelected = _currentMappings[featureId]?.contains(field) ?? false;
                  return ListTile(
                    dense: true,
                    title: Text(field, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                    onTap: () {
                      if (!isSelected) {
                        _addMapping(featureId, field);
                        Navigator.pop(context);
                      }
                    },
                    trailing: isSelected ? const Icon(Icons.check, size: 14, color: Colors.green) : null,
                  );
                }).toList(),
              );
            }).toList(),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text("Close")),
        ],
      ),
    );
  }

  Widget _buildStatusChip(bool active) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: active ? Colors.green.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        active ? 'ACTIVE' : 'DRAFT',
        style: TextStyle(
          color: active ? Colors.green : Colors.orange,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildPanelHeader(String title, IconData icon) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Colors.grey.shade200)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.blue),
          const SizedBox(width: 12),
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.black87),
          ),
        ],
      ),
    );
  }
}
