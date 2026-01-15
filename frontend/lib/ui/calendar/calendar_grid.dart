import 'dart:ui';
import 'package:flutter/services.dart'; // Added for HapticFeedback
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'dart:async'; // Added for Timer
import '../../blocs/schedule_bloc.dart';
import '../../repositories/schedule_repository.dart';
import '../components/impact_toast.dart';
import '../../models/agent_models.dart';
import '../theme/app_theme.dart';
import 'shift_card.dart';

class CalendarGrid extends StatefulWidget {
  final Map<String, dynamic> scheduleData;

  const CalendarGrid({super.key, required this.scheduleData});

  @override
  State<CalendarGrid> createState() => _CalendarGridState();
}

class _CalendarGridState extends State<CalendarGrid> {
  // Toast State
  bool _showToast = false;
  String _toastMessage = "";
  Timer? _toastTimer;

  void _triggerToast(String message) {
    if (_toastTimer != null) _toastTimer!.cancel();
    setState(() {
      _showToast = true;
      _toastMessage = message;
    });
    _toastTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _showToast = false);
    });
  }

  @override
  void dispose() {
    _toastTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    final state = context.watch<ScheduleBloc>().state;
    if (state is! ScheduleLoaded) {
      return const Center(child: CircularProgressIndicator());
    }

    final employees = state.employees;
    final unavailabilities = state.unavailabilities;
    final List<dynamic> shifts = widget.scheduleData['schedule'] ?? [];

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 100, 20, 20),
      child: Container(
        decoration: AppTheme.glassDecoration(),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
            child: Stack(
              children: [
                // 1. The Living Grid: Heatmap Background
                Positioned.fill(
                  child: CustomPaint(
                    painter: HeatmapPainter(
                      shifts: shifts,
                      config: state.demandConfig,
                    ),
                  ),
                ),
                
                // 2. Content
                SingleChildScrollView(
                  child: Column(
                    children: [
                      // Modern Header Row
                      Container(
                        padding: const EdgeInsets.symmetric(vertical: 24),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.03),
                          border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.08))),
                        ),
                        child: Row(
                          children: [
                            SizedBox(width: 120, child: Center(child: Text("EMPLOYEE", style: TextStyle(color: AppTheme.textSecondary, fontWeight: FontWeight.w900, fontSize: 10, letterSpacing: 1.5)))),
                            for (var day in days) 
                              Expanded(child: Center(child: Text(day.toUpperCase(), style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 2, fontSize: 11, color: AppTheme.textPrimary)))),
                          ],
                        ),
                      ),
                      // Employee Rows
                      for (var emp in employees)
                        Container(
                          decoration: BoxDecoration(
                            border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.04))),
                          ),
                          child: Row(
                            children: [
                              Draggable<String>(
                                data: emp.id,
                                feedback: Material(
                                  color: Colors.transparent,
                                  child: Container(
                                    width: 120,
                                    height: 50,
                                    decoration: BoxDecoration(
                                      color: AppTheme.surface,
                                      borderRadius: BorderRadius.circular(12),
                                      boxShadow: [BoxShadow(color: AppTheme.primary.withOpacity(0.4), blurRadius: 20)],
                                    ),
                                    alignment: Alignment.center,
                                    child: Text(emp.name, style: TextStyle(fontWeight: FontWeight.w800, color: AppTheme.textPrimary, decoration: TextDecoration.none, fontSize: 14)),
                                  ),
                                ),
                                childWhenDragging: Opacity(opacity: 0.3, child: Container(
                                  width: 120,
                                  height: 90,
                                  alignment: Alignment.center,
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Text(emp.name, style: TextStyle(fontWeight: FontWeight.w800, color: AppTheme.textPrimary, fontSize: 14)),
                                      if (emp.roles.isNotEmpty)
                                        Text(emp.roles.first.toUpperCase(), style: TextStyle(color: AppTheme.textSecondary, fontSize: 9, fontWeight: FontWeight.w900, letterSpacing: 1)),
                                    ],
                                  ),
                                )),
                                child: Container(
                                  width: 120,
                                  height: 90,
                                  alignment: Alignment.center,
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Text(emp.name, style: TextStyle(fontWeight: FontWeight.w800, color: AppTheme.textPrimary, fontSize: 14)),
                                      if (emp.roles.isNotEmpty)
                                        Text(emp.roles.first.toUpperCase(), style: TextStyle(color: AppTheme.textSecondary, fontSize: 9, fontWeight: FontWeight.w900, letterSpacing: 1)),
                                    ],
                                  ),
                                ),
                              ),
                              for (int d = 0; d < 7; d++)
                                Expanded(
                                  child: GestureDetector(
                                    onLongPress: () {
                                      final baseDate = DateTime.parse("2024-01-01"); 
                                      final targetDate = baseDate.add(Duration(days: d));
                                      context.read<ScheduleBloc>().add(ToggleUnavailability(emp.id, targetDate));
                                    },
                                    child: DragTarget<String>(
                                      onWillAccept: (droppedId) {
                                        if (droppedId == null) return false;
                                        final droppedEmp = employees.firstWhere((e) => e.id == droppedId, orElse: () => emp);
                                        
                                        final cellShifts = shifts.where((s) {
                                          try {
                                            if (s['date'] == null) return false;
                                            final shiftDate = DateTime.parse(s['date']);
                                            final weekday = shiftDate.weekday; 
                                            return s['employee_id'] == emp.id && (weekday - 1) == d;
                                          } catch (e) { return false; }
                                        }).toList();

                                        if (cellShifts.isNotEmpty) {
                                          final requiredRole = cellShifts.first['role'];
                                          final matches = droppedEmp.roles.contains(requiredRole) || droppedEmp.role == requiredRole;
                                          
                                          if (matches) {
                                            HapticFeedback.lightImpact(); 
                                          } else {
                                            HapticFeedback.heavyImpact(); 
                                          }
                                        }
                                        return true;
                                      },
                                      onAccept: (droppedId) {
                                        HapticFeedback.selectionClick();
                                        context.read<ScheduleRepository>().logFeedback(
                                          shiftId: "drag_${emp.id}_$d",
                                          droppedEmployeeId: droppedId,
                                          replacedEmployeeId: emp.id,
                                          shiftStart: DateTime.now(),
                                          role: "Role",
                                        );
                                        // Show Synapse Feedback
                                        _triggerToast("Preferenza Salvata! 🧠");
                                      },
                                      builder: (context, candidates, rejects) {
                                        final dateStr = DateTime.parse("2024-01-01").add(Duration(days: d)).toIso8601String().split('T')[0];
                                        final isUnavailable = unavailabilities.any((u) => u['employee_id'] == emp.id && u['date'] == dateStr);

                                        final cellShifts = shifts.where((s) {
                                          try {
                                            if (s['date'] == null) return false;
                                            final shiftDate = DateTime.parse(s['date']);
                                            final weekday = shiftDate.weekday; 
                                            final gridDayIdx = (weekday - 1); 
                                            return s['employee_id'] == emp.id && gridDayIdx == d;
                                          } catch (e) {
                                            return false;
                                          }
                                        }).toList();
                                        
                                        // Interaction Feedback
                                        Color borderColor = Colors.white.withOpacity(0.05);
                                        Color bgColor = isUnavailable 
                                              ? Colors.red.withOpacity(0.08)
                                              : (candidates.isNotEmpty ? AppTheme.primary.withOpacity(0.2) : Colors.transparent);
                                        double scale = 1.0;

                                        if (candidates.isNotEmpty) {
                                            final StringDroppedId = candidates.first!;
                                            final droppedEmp = employees.firstWhere((e) => e.id == StringDroppedId, orElse: () => emp);
                                            
                                            bool isMatch = true;
                                            if (cellShifts.isNotEmpty) {
                                                final requiredRole = cellShifts.first['role'];
                                                isMatch = droppedEmp.roles.contains(requiredRole) || droppedEmp.role == requiredRole;
                                            }
                                            
                                            if (isMatch) {
                                                // Attraction
                                                borderColor = Colors.greenAccent.withOpacity(0.8);
                                                bgColor = Colors.greenAccent.withOpacity(0.1);
                                                scale = 1.05;
                                            } else {
                                                // Resistance
                                                borderColor = Colors.redAccent.withOpacity(0.8);
                                                bgColor = Colors.redAccent.withOpacity(0.1);
                                                scale = 0.95;
                                            }
                                        }

                                        return Transform.scale(
                                          scale: scale,
                                          child: Container(
                                            height: 90,
                                            margin: const EdgeInsets.all(6),
                                            decoration: BoxDecoration(
                                              color: bgColor,
                                              borderRadius: BorderRadius.circular(14),
                                              border: Border.all(
                                                color: isUnavailable ? Colors.red.withOpacity(0.2) : borderColor,
                                                width: candidates.isNotEmpty ? 2 : 1,
                                              ),
                                            ),
                                            child: Center(
                                              child: isUnavailable
                                                ? const Text("OFF", style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.w900, fontSize: 9, letterSpacing: 1))
                                                : (cellShifts.isEmpty 
                                                    ? const SizedBox()
                                                    : Column(
                                                        mainAxisAlignment: MainAxisAlignment.center,
                                                        children: cellShifts.map((s) => ShiftCard(
                                                          label: s['role'] ?? "Role",
                                                          startTime: s['start_time'],
                                                          endTime: s['end_time'],
                                                          affinity: s['affinity']?.toDouble(),
                                                        )).toList(),
                                                      )),
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
                
                ImpactToast(message: _toastMessage, isVisible: _showToast),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HeatmapPainter extends CustomPainter {
  final List<dynamic> shifts;
  final DemandConfig config;

  HeatmapPainter({required this.shifts, required this.config});

  @override
  void paint(Canvas canvas, Size size) {
    const double sidebarWidth = 120.0;
    final double dayWidth = (size.width - sidebarWidth) / 7;

    Map<int, int> shiftsPerDay = {};
    for (int i = 0; i < 7; i++) shiftsPerDay[i] = 0;

    for (var s in shifts) {
      if (s['date'] == null) continue;
      try {
        final date = DateTime.parse(s['date']);
        final dayIdx = date.weekday - 1;
        if (dayIdx >= 0 && dayIdx < 7) {
          shiftsPerDay[dayIdx] = (shiftsPerDay[dayIdx] ?? 0) + 1;
        }
      } catch (e) {
        // ignore
      }
    }

    for (int i = 0; i < 7; i++) {
      final double left = sidebarWidth + (i * dayWidth);
      final Rect rect = Rect.fromLTWH(left, 0, dayWidth, size.height);
      
      final int count = shiftsPerDay[i] ?? 0;
      
      // Dynamic Logic based on user config
      // Weekday (0-4), Weekend (5-6)
      final bool isWeekend = (i >= 5);
      final int target = isWeekend ? config.weekendTarget : config.weekdayTarget;
      
      List<Color> gradientColors;
      
      // Tolerance of +/- 1 (Strict would be != target)
      if (count < target - 1) {
        // Critical: Red (Understaffed)
        gradientColors = [
          Colors.redAccent.withOpacity(0.15),
          Colors.redAccent.withOpacity(0.05),
        ];
      } else if (count > target + 1) {
        // Excess: Blue (Overstaffed)
        gradientColors = [
          Colors.blueAccent.withOpacity(0.15),
          Colors.blueAccent.withOpacity(0.05),
        ];
      } else {
        // Optimal: Green
        gradientColors = [
          Colors.greenAccent.withOpacity(0.15),
          Colors.greenAccent.withOpacity(0.05),
        ];
      }

      final paint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: gradientColors,
        ).createShader(rect);

      canvas.drawRect(rect, paint);
    }
  }

  @override
  bool shouldRepaint(covariant HeatmapPainter oldDelegate) {
    return oldDelegate.shifts != shifts || oldDelegate.config != config;
  }
}
