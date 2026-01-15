
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
                  Icon(Icons.tune_rounded, color: AppTheme.primary, size: 24),
                  const SizedBox(width: 12),
                  Text(
                    "Demand Constraints",
                    style: TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              
              // Weekday Slider
              _buildSliderParams(
                "Weekday Target", 
                "Minimum staff Mon-Fri", 
                _weekdayTarget, 
                (val) => setState(() => _weekdayTarget = val.toInt())
              ),
              
              const SizedBox(height: 20),

              // Weekend Slider
              _buildSliderParams(
                "Weekend Target", 
                "Minimum staff Sat-Sun", 
                _weekendTarget, 
                (val) => setState(() => _weekendTarget = val.toInt())
              ),

              const SizedBox(height: 24),

              // AI Toggle (Future)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.aiGlow.withOpacity(0.05),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.aiGlow.withOpacity(0.2)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.auto_awesome, color: AppTheme.aiGlow, size: 20),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("AI Auto-Pilot", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold, fontSize: 13)),
                          Text("Learn from history", style: TextStyle(color: Colors.white54, fontSize: 11)),
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
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text("AI is analyzing your history..."), duration: Duration(seconds: 1)),
                          );
                        }
                      },
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Text("Cancel", style: TextStyle(color: AppTheme.textSecondary)),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                    ),
                    onPressed: () {
                      context.read<ScheduleBloc>().add(UpdateDemandConfig(
                        DemandConfig(
                          weekdayTarget: _weekdayTarget,
                          weekendTarget: _weekendTarget,
                          aiEnabled: _aiEnabled,
                        )
                      ));
                      Navigator.pop(context);
                    },
                    child: const Text("Apply Changes", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSliderParams(String title, String subt, int value, Function(double) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
                Text(subt, style: TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
              ],
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(6)),
              child: Text("$value", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
        SliderTheme(
          data: SliderThemeData(
            activeTrackColor: AppTheme.primary,
            inactiveTrackColor: Colors.white10,
            thumbColor: Colors.white,
            overlayColor: AppTheme.primary.withOpacity(0.2),
          ),
          child: Slider(
            value: value.toDouble(),
            min: 1,
            max: 10,
            divisions: 9,
            onChanged: onChanged,
          ),
        ),
      ],
    );
  }
}
