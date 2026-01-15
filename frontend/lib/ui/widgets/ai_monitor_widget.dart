import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../repositories/schedule_repository.dart';
import '../theme/app_theme.dart';
import '../settings/training_progress_dialog.dart';

class AiMonitorWidget extends StatefulWidget {
  const AiMonitorWidget({super.key});

  @override
  State<AiMonitorWidget> createState() => _AiMonitorWidgetState();
}

class _AiMonitorWidgetState extends State<AiMonitorWidget> {
  bool _isTraining = false;
  String _status = "Ready to Learn";
  double? _lastLoss;

  Future<void> _startTraining() async {
    await TrainingProgressDialog.show(context);
    setState(() {
      _status = "Training Complete";
    });
  }

  @override
  Widget build(BuildContext context) {
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
              Icon(Icons.psychology_rounded, color: AppTheme.accent),
              const SizedBox(width: 10),
              Text("AI MONITOR", style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontSize: 16, letterSpacing: 1)),
            ],
          ),
          const Divider(height: 30, color: Colors.white10),
          _buildStatRow("Status", _status),
          if (_lastLoss != null) _buildStatRow("Last Loss", _lastLoss!.toStringAsFixed(4)),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: _isTraining ? Colors.grey : AppTheme.accent.withOpacity(0.2),
                foregroundColor: AppTheme.accent,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: _isTraining ? null : _startTraining,
              icon: _isTraining 
                ? SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent))
                : const Icon(Icons.model_training_rounded),
              label: Text(_isTraining ? "TRAINING..." : "RETRAIN ENGINE"),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          Text(value, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.bold, fontSize: 12)),
        ],
      ),
    );
  }
}
