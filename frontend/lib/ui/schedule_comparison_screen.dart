import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../repositories/schedule_repository.dart';
import 'theme/app_theme.dart';
import '../models/agent_models.dart';

class ScheduleComparisonScreen extends StatefulWidget {
  final ScheduleRepository repository;

  const ScheduleComparisonScreen({super.key, required this.repository});

  @override
  State<ScheduleComparisonScreen> createState() => _ScheduleComparisonScreenState();
}

class _ScheduleComparisonScreenState extends State<ScheduleComparisonScreen> {
  DateTime _selectedMonth = DateTime(DateTime.now().year, DateTime.now().month, 1);
  List<dynamic> _realHistory = [];
  List<dynamic> _aiSimulation = [];
  bool _isLoading = false;
  String? _loadingMessage;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Future<void> _fetchData() async {
    setState(() {
      _isLoading = true;
      _loadingMessage = "Recupero storico reale...";
    });

    try {
      final start = _selectedMonth;
      final end = DateTime(_selectedMonth.year, _selectedMonth.month + 1, 0);
      
      final history = await widget.repository.getHistoricalSchedule(start, end);
      
      setState(() {
        _realHistory = history;
        _aiSimulation = [];
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Errore: $e")));
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _runSimulation() async {
    setState(() {
      _isLoading = true;
      _loadingMessage = "IA sta calcolando il miglior scenario...";
    });

    try {
      final start = _selectedMonth;
      final end = DateTime(_selectedMonth.year, _selectedMonth.month + 1, 0);
      
      final employees = await widget.repository.getEmployment();
      final activities = await widget.repository.getActivities();

      // Trigger retraining first, as required for coherence
      try { await widget.repository.retrain(); } catch(e) {}

      int attempts = 0;
      while (attempts < 180) {
        final status = await widget.repository.getTrainingProgress();
        if (status['status'] != 'running' && attempts > 2) break;
        
        setState(() {
          _loadingMessage = "Apprendimento IA in corso... (${((status['progress'] ?? 0.0) * 100).toStringAsFixed(0)}%)";
        });
        await Future.delayed(const Duration(seconds: 1));
        attempts++;
      }

      setState(() => _loadingMessage = "Ottimizzazione in corso...");
      final result = await widget.repository.triggerGeneration(
        startDate: start,
        endDate: end,
        employees: employees,
        activities: activities,
      );

      setState(() {
        _aiSimulation = result['schedule'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Errore simulazione: $e")));
        setState(() => _isLoading = false);
      }
    }
  }

  void _changeMonth(int delta) {
    setState(() {
      int newMonth = _selectedMonth.month + delta;
      int newYear = _selectedMonth.year;
      
      while (newMonth > 12) {
        newMonth -= 12;
        newYear += 1;
      }
      while (newMonth < 1) {
        newMonth += 12;
        newYear -= 1;
      }
      
      _selectedMonth = DateTime(newYear, newMonth, 1);
    });
    _fetchData();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text("ANALISI & CONFRONTO MIA"),
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome_motion_rounded, color: AppTheme.aiGlow),
            tooltip: "Simula Scenario Migliore",
            onPressed: _isLoading ? null : _runSimulation,
          ),
          IconButton(
            icon: const Icon(Icons.calendar_month_rounded),
            onPressed: () async {
              final picked = await showDatePicker(
                context: context,
                initialDate: _selectedMonth,
                firstDate: DateTime(2020),
                lastDate: DateTime(2030),
              );
              if (picked != null) {
                setState(() => _selectedMonth = DateTime(picked.year, picked.month, 1));
                _fetchData();
              }
            },
          ),
        ],
      ),
      body: Stack(
        children: [
          Column(
            children: [
              _buildNavigationHeader(),
              _buildWeekdayLabels(),
              Expanded(
                child: _buildCalendarGrid(),
              ),
            ],
          ),
          if (_isLoading)
            Container(
              color: Colors.black54,
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(color: AppTheme.aiGlow),
                    const SizedBox(height: 20),
                    Text(_loadingMessage ?? "Attendere...", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildNavigationHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.02),
        border: const Border(bottom: BorderSide(color: Colors.white10)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.chevron_left_rounded, color: Colors.white),
                onPressed: () => _changeMonth(-1),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    DateFormat('MMMM yyyy').format(_selectedMonth).toUpperCase(),
                    style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w900, letterSpacing: 1),
                  ),
                  const Text("Analisi performance vs reale", style: TextStyle(color: Colors.white38, fontSize: 11)),
                ],
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.chevron_right_rounded, color: Colors.white),
                onPressed: () => _changeMonth(1),
              ),
            ],
          ),
          if (_aiSimulation.isEmpty && !_isLoading)
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.aiGlow.withOpacity(0.1),
                side: const BorderSide(color: AppTheme.aiGlow),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: _runSimulation,
              child: const Text("SIMULA OTTIMIZZAZIONE", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold)),
            ),
        ],
      ),
    );
  }

  Widget _buildWeekdayLabels() {
    final days = ["LUN", "MAR", "MER", "GIO", "VEN", "SAB", "DOM"];
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      color: Colors.white.withOpacity(0.01),
      child: Row(
        children: days.map((d) => Expanded(
          child: Center(child: Text(d, style: const TextStyle(color: Colors.white24, fontSize: 10, fontWeight: FontWeight.w900, letterSpacing: 1.5)))
        )).toList(),
      ),
    );
  }

  Widget _buildCalendarGrid() {
    final firstDayOfMonth = _selectedMonth;
    final lastDayOfMonth = DateTime(_selectedMonth.year, _selectedMonth.month + 1, 0);
    
    // Calculate padding
    final startPadding = (firstDayOfMonth.weekday - 1); // 0 for Monday
    final totalDays = lastDayOfMonth.day;
    
    return GridView.builder(
      padding: const EdgeInsets.all(1),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 7,
        childAspectRatio: 0.8,
        crossAxisSpacing: 1,
        mainAxisSpacing: 1,
      ),
      itemCount: 42, // Fix grid slots
      itemBuilder: (context, index) {
        final dayNumber = index - startPadding + 1;
        if (dayNumber < 1 || dayNumber > totalDays) {
          return Container(color: Colors.white.withOpacity(0.015));
        }

        final date = DateTime(_selectedMonth.year, _selectedMonth.month, dayNumber);
        final dateStr = DateFormat('yyyy-MM-dd').format(date);
        
        final dayReal = _realHistory.where((i) => (i['date'] ?? i['tmregister']?.toString().substring(0,10)) == dateStr).toList();
        final dayAi = _aiSimulation.where((i) => i['date'] == dateStr).toList();

        return _buildCalendarCell(date, dayReal, dayAi);
      },
    );
  }

  Widget _buildCalendarCell(DateTime date, List<dynamic> real, List<dynamic> ai) {
    final isToday = DateFormat('yyyy-MM-dd').format(date) == DateFormat('yyyy-MM-dd').format(DateTime.now());

    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.02),
        border: Border.all(color: isToday ? AppTheme.aiGlow.withOpacity(0.3) : Colors.white.withOpacity(0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(6),
            child: Text(
              date.day.toString(),
              style: TextStyle(
                color: isToday ? AppTheme.aiGlow : Colors.white38, 
                fontWeight: FontWeight.bold,
                fontSize: 12
              ),
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Column(
                children: [
                  if (real.isNotEmpty) ...[
                    _buildMiniBadge("REALE", real.length, Colors.blueGrey),
                    const SizedBox(height: 2),
                  ],
                  if (ai.isNotEmpty) ...[
                    _buildMiniBadge("IA", ai.length, AppTheme.aiGlow),
                  ],
                  if (real.isNotEmpty || ai.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    _buildComparisonIndicator(real, ai),
                  ],
                ],
              ),
            ),
          ),
          InkWell(
            onTap: () => _showDayDetails(date, real, ai),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 2),
              color: Colors.white.withOpacity(0.05),
              child: const Icon(Icons.more_horiz, size: 14, color: Colors.white24),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMiniBadge(String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: TextStyle(color: color, fontSize: 7, fontWeight: FontWeight.w900)),
          const SizedBox(width: 4),
          Text(count.toString(), style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildComparisonIndicator(List<dynamic> real, List<dynamic> ai) {
    if (ai.isEmpty) return const SizedBox();
    
    // Simple heuristic: if AI assigned less people or shifted them to better hours
    final diff = ai.length - real.length;
    final color = diff < 0 ? Colors.greenAccent : (diff > 0 ? Colors.orangeAccent : Colors.white24);
    final icon = diff < 0 ? Icons.trending_down_rounded : (diff > 0 ? Icons.trending_up_rounded : Icons.check_circle_outline_rounded);

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 10, color: color),
        const SizedBox(width: 4),
        Text(
          diff == 0 ? "SMART" : "${diff > 0 ? '+' : ''}$diff STAFF",
          style: TextStyle(color: color, fontSize: 7, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }

  void _showDayDetails(DateTime date, List<dynamic> real, List<dynamic> ai) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF111827),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Text(
              DateFormat('EEEE d MMMM yyyy').format(date).toUpperCase(),
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 16),
            ),
            const SizedBox(height: 24),
            Expanded(
              child: Row(
                children: [
                  Expanded(child: _buildDetailList("REALE", real, Colors.blueGrey)),
                  const VerticalDivider(color: Colors.white10),
                  Expanded(child: _buildDetailList("OTTIMIZZATO IA", ai, AppTheme.aiGlow)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailList(String title, List<dynamic> items, Color accent) {
    return Column(
      children: [
        Text(title, style: TextStyle(color: accent, fontSize: 10, fontWeight: FontWeight.w900, letterSpacing: 1)),
        const SizedBox(height: 12),
        Expanded(
          child: items.isEmpty
            ? const Center(child: Text("Nessun dato", style: TextStyle(color: Colors.white24, fontSize: 12)))
            : ListView.builder(
                itemCount: items.length,
                itemBuilder: (context, index) {
                  final item = items[index];
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.04),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item['employee_name'] ?? "Sconosciuto", style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold)),
                        Text("${item['start_time']} - ${item['end_time']}", style: const TextStyle(color: Colors.white38, fontSize: 10)),
                      ],
                    ),
                  );
                },
              ),
        ),
      ],
    );
  }
}
