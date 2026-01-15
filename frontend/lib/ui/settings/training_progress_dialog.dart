import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../repositories/schedule_repository.dart';
import '../theme/app_theme.dart';

class TrainingProgressDialog extends StatefulWidget {
  final Future<void> Function() onStart;

  const TrainingProgressDialog({super.key, required this.onStart});

  static Future<void> show(BuildContext context) {
    return showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => TrainingProgressDialog(
        onStart: context.read<ScheduleRepository>().triggerRetraining,
      ),
    );
  }

  @override
  State<TrainingProgressDialog> createState() => _TrainingProgressDialogState();
}

class _TrainingProgressDialogState extends State<TrainingProgressDialog> {
  Timer? _timer;
  double _progress = 0.0;
  String _message = "Initializing...";
  String _status = "starting";
  Map<String, dynamic> _details = {};

  @override
  void initState() {
    super.initState();
    _startProcess();
  }

  Future<void> _startProcess() async {
    try {
      // 1. Trigger Backend
      await widget.onStart();
      
      // 2. Start Polling
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
         _pollProgress();
      });

    } catch (e) {
      if (mounted) setState(() {
        _message = "Failed to start: $e";
        _status = "error";
      });
    }
  }

  Future<void> _pollProgress() async {
    try {
      final repo = context.read<ScheduleRepository>();
      final data = await repo.getTrainingProgress();
      
      if (mounted) {
        setState(() {
          _status = data['status'] ?? "unknown";
          _progress = (data['progress'] ?? 0.0).toDouble();
          _message = data['message'] ?? "Processing...";
          _details = data['details'] ?? {};
        });

        if (_status == 'complete') {
          _timer?.cancel();
          await Future.delayed(const Duration(seconds: 2)); // Show 100% briefly
          if (mounted) Navigator.pop(context);
        }
        
        if (_status == 'error') {
          _timer?.cancel();
        }
      }
    } catch (e) {
      print("Polling error: $e");
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    bool isError = _status == "error";

    return AlertDialog(
      backgroundColor: const Color(0xFF1E1E2C),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Colors.white.withOpacity(0.1))),
      title: Row(
        children: [
          Icon(isError ? Icons.error_outline : Icons.psychology, color: isError ? Colors.redAccent : AppTheme.aiGlow),
          const SizedBox(width: 12),
          Text(isError ? "Training Error" : "Global Brain Training", style: const TextStyle(color: Colors.white, fontSize: 18)),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(_message, style: const TextStyle(color: Colors.white70, fontSize: 14)),
          const SizedBox(height: 20),
          LinearProgressIndicator(
            value: _status == "starting" ? null : _progress, // Indeterminate at start
            backgroundColor: Colors.white10,
            color: isError ? Colors.redAccent : AppTheme.aiGlow,
            minHeight: 8,
            borderRadius: BorderRadius.circular(4),
          ),
          const SizedBox(height: 10),
          if (_details.isNotEmpty)
            Text(
              "Processed: ${_details['envs_processed'] ?? 0} envs | Samples: ${_details['total_samples'] ?? 0}",
              style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 10),
            ),
        ],
      ),
      actions: [
        if (isError)
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("CLOSE", style: TextStyle(color: Colors.white54)),
          ),
      ],
    );
  }
}
