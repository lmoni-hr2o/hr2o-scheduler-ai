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
  final DateTime startDate; // New: Controls the visible week

  const CalendarGrid({
    super.key, 
    required this.scheduleData,
    required this.startDate,
  });

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

  String _normalizeName(String? name) {
    if (name == null || name.isEmpty) return "";
    // Remove symbols, uppercase, split, sort, join to catch word swaps
    final clean = name.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9\s]'), '');
    final words = clean.trim().split(RegExp(r'\s+'))..sort();
    return words.join(' ');
  }

  @override
  Widget build(BuildContext context) {
    final days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    final state = context.watch<ScheduleBloc>().state;
    if (state is! ScheduleLoaded) {
      return const Center(child: CircularProgressIndicator());
    }

    final s = state;
    // FIXED: Deduplicate primarily by normalized name to handle multiple sync IDs and word swaps
    final seenNames = <String>{};
    final activeEmployees = s.employees.where((e) {
      final nameKey = _normalizeName(e.fullName);
      if (nameKey.isEmpty || seenNames.contains(nameKey)) return false;
      seenNames.add(nameKey);
      return true;
    }).toList();
    
    final unavailabilities = s.unavailabilities;
    final List<dynamic> shifts = widget.scheduleData['schedule'] ?? widget.scheduleData['result'] ?? [];
    
    // Index activities for fast lookup
    final Map<String, String> activityNameMap = {
      for (var a in s.activities) a.id.toString(): a.name
    };

    // Performance Optimization: Pre-index shifts by (employeeId or name) + date
    final Map<String, List<dynamic>> shiftCache = {};
    for (var s in shifts) {
      if (s['date'] == null) continue;
      final String d = s['date'].toString();
      final String? eid = s['employee_id']?.toString();
      final String name = _normalizeName(s['employee_name']?.toString());
      
      if (eid != null && eid != "unassigned") {
        shiftCache.putIfAbsent("${eid}_$d", () => []).add(s);
      }
      if (name.isNotEmpty) {
        shiftCache.putIfAbsent("${name}_$d", () => []).add(s);
      }
    }

    if (shifts.isNotEmpty && DateTime.now().second % 10 == 0) {
       debugPrint("DIAGNOSTIC: CalendarGrid displaying ${shifts.length} shifts. Sample date: ${shifts.first['date']}");
    }

    // Use passed startDate (aligned to Monday by parent)
    final DateTime weekStart = widget.startDate;

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
                      weekStart: weekStart,
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
                          _buildEmployeeRow(emp, shifts, unavailabilities, s.employees, s, days, weekStart, shiftCache),
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

  Widget _buildEmployeeRow(Employment emp, List<dynamic> shifts, List unavailabilities, List<Employment> employees, ScheduleLoaded state, List<String> days, DateTime weekStart, Map<String, List<dynamic>> shiftCache) {
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.04))),
      ),
      child: Row(
        children: [
          // Sidebar: Employee Name
          InkWell(
            onTap: () => _showEmployeeProfile(context, emp),
            child: SizedBox(
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
                  const SizedBox(height: 4),
                  // Contract Badge
                  if (emp.contractType != null)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.05),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: Colors.white.withOpacity(0.1)),
                    ),
                    child: Text(
                      "${emp.contractType ?? ''} ${emp.contractHours != null ? '${emp.contractHours!.toInt()}h' : ''}",
                      style: const TextStyle(color: AppTheme.accent, fontSize: 7, fontWeight: FontWeight.bold),
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
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
                    final isUnavailable = unavailabilities.any((u) {
                      final bool matchId = u['employee_id']?.toString() == emp.id.toString();
                      // Fallback case: if unavailability was linked to an alternative ID, it might not match by ID 
                      // but we assume it follows the person's name or the provided employee reference matches.
                      return matchId && u['date'] == dateStr;
                    });

                    final cellShifts = <dynamic>[];
                    // Fast lookup in cache
                    final idKey = "${emp.id}_$dateStr";
                    final nameKey = "${_normalizeName(emp.fullName)}_$dateStr";
                    
                    if (shiftCache.containsKey(idKey)) {
                      cellShifts.addAll(shiftCache[idKey]!);
                    } else if (shiftCache.containsKey(nameKey)) {
                      cellShifts.addAll(shiftCache[nameKey]!);
                    }
                    
                    final hasHistory = state.historicalSchedules.any((hp) {
                      final bool matchId = hp['employee_id'] == emp.id;
                      final String histName = _normalizeName(hp['fullName']?.toString());
                      final String rowName = _normalizeName(emp.fullName);
                      final bool matchName = histName.isNotEmpty && histName == rowName;
                      return (matchId || matchName) && hp['date'] == dateStr;
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
                                            absenceRisk: s['absence_risk']?.toDouble(),
                                            historicalTime: histTime,
                                            activities: state.activities,
                                            activityNameMap: activityNameMap, // Pass optimized map
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

  void _showEmployeeProfile(BuildContext context, Employment emp) {

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            CircleAvatar(
              backgroundColor: AppTheme.primary,
              child: Text(emp.fullName.isNotEmpty ? emp.fullName[0] : "?", style: const TextStyle(color: Colors.white)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(emp.fullName, style: const TextStyle(color: Colors.white, fontSize: 16)),
                  Text(emp.role, style: const TextStyle(color: Colors.grey, fontSize: 12)),
                ],
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Divider(color: Colors.white24),
            const SizedBox(height: 8),
            _buildProfileRow("Tipo Contratto", emp.contractType ?? "N/D"),
            _buildProfileRow("Ore Settimanali", emp.contractHours != null ? "${emp.contractHours}h" : "N/D"),
            _buildProfileRow("Qualifica", emp.qualification ?? "N/D"),
            _buildProfileRow("Azienda", emp.name),
            _buildProfileRow("Data Assunzione", emp.bornDate != null ? emp.bornDate!.substring(0, 10) : "N/D"), // Using bornDate as placeholder if dtHired is missing in Model
            const SizedBox(height: 16),
            const Text("Performance & AI", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            _buildProfileRow("Keyword Clienti", emp.customerKeywords.isNotEmpty ? emp.customerKeywords.join(", ") : "Nessuna"),
          ],
        ),
        actions: [
          TextButton(
            child: const Text("CHIUDI", style: TextStyle(color: Colors.white)),
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12)),
          Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12)),
        ],
      ),
    );
  }
}

class HeatmapPainter extends CustomPainter {
  final List<dynamic> shifts;
  final DemandConfig config;
  final DateTime weekStart; // NEW

  HeatmapPainter({required this.shifts, required this.config, required this.weekStart});

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
        
        // Match ONLY shifts in the visible week
        final diff = date.difference(weekStart).inDays;
        if (diff >= 0 && diff < 7) {
          shiftsPerDay[diff] = (shiftsPerDay[diff] ?? 0) + 1;
        }
      } catch (e) { }
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
      
      // Tolerance of +/- 2 (Previously 1) to avoid excessive red alerts on slight deviations
      if (count < target - 2) {
        // Critical: Red (Understaffed)
        gradientColors = [
          AppTheme.danger.withOpacity(0.15),
          AppTheme.danger.withOpacity(0.05),
        ];
      } else if (count > target + 2) {
        // Excess: Indigo (Overstaffed)
        gradientColors = [
          AppTheme.primary.withOpacity(0.15),
          AppTheme.primary.withOpacity(0.05),
        ];
      } else {
        // Optimal: Green
        gradientColors = [
          AppTheme.accent.withOpacity(0.15),
          AppTheme.accent.withOpacity(0.05),
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
