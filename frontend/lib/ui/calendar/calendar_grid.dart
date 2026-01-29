import 'dart:ui';
import 'package:intl/intl.dart';
import 'package:flutter/services.dart'; 
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

    final s = state;
    // FIXED: Show all employees, not just those with history.
    // The previous filter hidden employees causing "invisible shifts".
    final activeEmployees = s.employees;
    
    final unavailabilities = s.unavailabilities;
    final List<dynamic> shifts = widget.scheduleData['schedule'] ?? [];

    // Calculate Week Start for real dates
    DateTime weekStart = DateTime.now().subtract(Duration(days: DateTime.now().weekday - 1));
    if (shifts.isNotEmpty) {
      try {
        final firstDate = DateTime.parse(shifts.first['date']);
        weekStart = firstDate.subtract(Duration(days: firstDate.weekday - 1));
      } catch (_) {}
    }

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
                Positioned.fill(
                  child: CustomPaint(
                    painter: HeatmapPainter(
                      shifts: shifts,
                      config: s.demandConfig,
                    ),
                  ),
                ),
                
                SingleChildScrollView(
                  child: Column(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(vertical: 24),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.03),
                          border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.08))),
                        ),
                        child: Row(
                          children: [
                            SizedBox(width: 140, child: Center(child: Text("EMPLOYEE", style: TextStyle(color: AppTheme.textSecondary, fontWeight: FontWeight.w900, fontSize: 10, letterSpacing: 1.5)))),
                            for (int i = 0; i < 7; i++) 
                              Expanded(
                                child: Center(
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        DateFormat('EEE').format(weekStart.add(Duration(days: i))).toUpperCase(),
                                        style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5, fontSize: 10, color: AppTheme.textPrimary.withOpacity(0.7)),
                                      ),
                                      Text(
                                        DateFormat('dd/MM').format(weekStart.add(Duration(days: i))),
                                        style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: AppTheme.textPrimary),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                      
                      if (activeEmployees.isNotEmpty)
                        for (var emp in activeEmployees)
                          _buildEmployeeRow(emp, shifts, unavailabilities, s.employees, s, days, weekStart),
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

  Widget _buildSectionHeader(String title, BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      color: Colors.white.withOpacity(0.02),
      child: Text(title, style: TextStyle(color: AppTheme.textSecondary.withOpacity(0.3), fontSize: 9, fontWeight: FontWeight.w900, letterSpacing: 1.5)),
    );
  }

  Widget _buildEmployeeRow(Employment emp, List<dynamic> shifts, List unavailabilities, List<Employment> employees, ScheduleLoaded state, List<String> days, DateTime weekStart) {
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.04))),
      ),
      child: Row(
        children: [
          // Sidebar: Employee Name
          SizedBox(
            width: 140,
            height: 100,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: AppTheme.accent.withOpacity(0.1),
                  child: Text(emp.fullName.isNotEmpty ? emp.fullName[0] : "?", style: const TextStyle(color: AppTheme.accent, fontSize: 10, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 6),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text(
                    emp.fullName.split(' ').first,
                    style: const TextStyle(color: AppTheme.textPrimary, fontSize: 10, fontWeight: FontWeight.w600),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(
                  emp.role.toUpperCase(),
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 7, fontWeight: FontWeight.w900, letterSpacing: 0.5),
                ),
              ],
            ),
          ),
          // Calendar Cells
          for (int d = 0; d < 7; d++)
            Expanded(
              child: Container(
                height: 100,
                decoration: BoxDecoration(
                  border: Border(left: BorderSide(color: Colors.white.withOpacity(0.04))),
                ),
                child: DragTarget<Map<String, dynamic>>(
                  onWillAccept: (droppedShift) => true,
                  onAccept: (droppedShift) {
                    HapticFeedback.selectionClick();
                    final dateStr = weekStart.add(Duration(days: d));
                    context.read<ScheduleBloc>().add(UpdateShift(
                      shift: droppedShift, 
                      newDate: dateStr, 
                      newEmployeeId: emp.id
                    ));
                    _triggerToast("Preferenza Salvata! 🧠");
                  },
                  builder: (context, candidates, rejects) {
                    final cellDate = weekStart.add(Duration(days: d));
                    final dateStr = cellDate.toIso8601String().split('T')[0];
                    final isUnavailable = unavailabilities.any((u) => u['employee_id'] == emp.id && u['date'] == dateStr);

                    final cellShifts = shifts.where((s) {
                      try {
                        if (s['date'] == null) return false;
                        final shiftDate = DateTime.parse(s['date']);
                        return s['employee_id'] == emp.id && shiftDate.year == cellDate.year && shiftDate.month == cellDate.month && shiftDate.day == cellDate.day;
                      } catch (e) { return false; }
                    }).toList();
                    
                    final hasHistory = state.historicalSchedules.any((hp) {
                      return hp['employee_id'] == emp.id && hp['date'] == dateStr;
                    });

                    Color borderColor = hasHistory ? Colors.amber.withOpacity(0.4) : Colors.white.withOpacity(0.05);
                    Color bgColor = isUnavailable 
                          ? Colors.red.withOpacity(0.08)
                          : (candidates.isNotEmpty ? AppTheme.primary.withOpacity(0.2) : Colors.transparent);
                    double scale = candidates.isNotEmpty ? 1.05 : 1.0;

                    return Transform.scale(
                      scale: scale,
                      child: Container(
                        height: 90,
                        constraints: const BoxConstraints(minHeight: 100),
                        decoration: BoxDecoration(
                          color: bgColor,
                          border: Border.all(color: borderColor),
                        ),
                        child: Stack(
                          children: [
                            if (hasHistory)
                              Positioned(
                                top: 4,
                                right: 4,
                                child: Container(
                                  width: 8,
                                  height: 8,
                                  decoration: BoxDecoration(
                                    color: Colors.amber, 
                                    shape: BoxShape.circle,
                                    boxShadow: [BoxShadow(color: Colors.amber.withOpacity(0.4), blurRadius: 4)],
                                  ),
                                ),
                              ),
                            Center(
                              child: isUnavailable
                                ? const Text("OFF", style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.w900, fontSize: 9))
                                : (cellShifts.isEmpty 
                                    ? const SizedBox()
                                    : Column(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: cellShifts.map((s) {
                                          final hist = state.historicalSchedules.firstWhere(
                                            (hp) => hp['employee_id'] == emp.id && hp['date'] == dateStr,
                                            orElse: () => null
                                          );
                                          String? histTime;
                                          if (hist != null) {
                                            histTime = "${hist['tmentry']} - ${hist['tmexit']}";
                                          }
                                          return ShiftCard(
                                            shift: s,
                                            affinity: s['affinity']?.toDouble(),
                                            historicalTime: histTime,
                                            activities: state.activities,
                                          );
                                        }).toList(),
                                      )),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
        ],
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
