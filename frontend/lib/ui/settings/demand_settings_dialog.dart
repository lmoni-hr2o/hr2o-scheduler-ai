
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../blocs/schedule_bloc.dart';
import '../../models/agent_models.dart';
import '../theme/app_theme.dart';

class DemandSettingsDialog extends StatefulWidget {
  const DemandSettingsDialog({super.key});

  @override
  State<DemandSettingsDialog> createState() => _DemandSettingsDialogState();
}

class _DemandSettingsDialogState extends State<DemandSettingsDialog> {
  int _weekdayTarget = 3;
  int _weekendTarget = 2;
  bool _aiEnabled = true;

  @override
  void initState() {
    super.initState();
    final state = context.read<ScheduleBloc>().state;
    if (state is ScheduleLoaded) {
      _weekdayTarget = state.demandConfig.weekdayTarget;
      _weekendTarget = state.demandConfig.weekendTarget;
      _aiEnabled = state.demandConfig.aiEnabled;
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<ScheduleBloc, ScheduleState>(
      listener: (context, state) {
        if (state is ScheduleLoaded) {
          setState(() {
            _weekdayTarget = state.demandConfig.weekdayTarget;
            _weekendTarget = state.demandConfig.weekendTarget;
            _aiEnabled = state.demandConfig.aiEnabled;
          });
        }
      },
      child: Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(20),
        child: Container(
          padding: const EdgeInsets.all(24),
          constraints: const BoxConstraints(maxWidth: 400),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.2),
                blurRadius: 20,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.auto_awesome_rounded, color: AppTheme.aiGlow, size: 24),
                  const SizedBox(width: 12),
                  Text(
                    "AI Scheduling",
                    style: TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                "Manual demand constraints are no longer needed. The system now automatically learns and predicts workload from your history.",
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 13, height: 1.5),
              ),
              const SizedBox(height: 24),
              
              // AI Toggle
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.aiGlow.withOpacity(0.05),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.aiGlow.withOpacity(0.2)),
                ),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppTheme.aiGlow.withOpacity(0.1),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(Icons.auto_awesome, color: AppTheme.aiGlow, size: 20),
                    ),
                    const SizedBox(width: 16),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("AI Demand Forecast", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold, fontSize: 14)),
                          SizedBox(height: 2),
                          Text("Analyzing patterns in REAL-TIME", style: TextStyle(color: Colors.white54, fontSize: 11)),
                        ],
                      ),
                    ),
                    Switch(
                      value: _aiEnabled, 
                      activeColor: AppTheme.aiGlow,
                      onChanged: (val) {
                        setState(() => _aiEnabled = val);
                        if (val) {
                          context.read<ScheduleBloc>().add(LearnDemand());
                        }
                      },
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primary,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        elevation: 0,
                      ),
                      onPressed: () {
                        context.read<ScheduleBloc>().add(UpdateDemandConfig(
                          DemandConfig(
                            weekdayTarget: _weekdayTarget, // Keep internal but no longer shown
                            weekendTarget: _weekendTarget,
                            aiEnabled: _aiEnabled,
                          )
                        ));
                        Navigator.pop(context);
                      },
                      child: const Text("CLOSE", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
