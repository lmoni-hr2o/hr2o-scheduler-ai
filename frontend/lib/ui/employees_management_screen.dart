import 'package:flutter/material.dart';
import '../models/agent_models.dart';
import '../repositories/schedule_repository.dart';
import '../services/labor_profile_service.dart';
import '../utils/security_utils.dart';
import 'theme/app_theme.dart';
import 'components/impact_toast.dart';

class EmployeesManagementScreen extends StatefulWidget {
  const EmployeesManagementScreen({super.key});

  @override
  State<EmployeesManagementScreen> createState() => _EmployeesManagementScreenState();
}

class _EmployeesManagementScreenState extends State<EmployeesManagementScreen> {
  final ScheduleRepository _repository = ScheduleRepository();
  final LaborProfileService _profileService = LaborProfileService();
  
  List<Employment> _employees = [];
  List<LaborProfile> _profiles = [];
  bool _isLoading = true;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final employees = await _repository.getEmployment();
      final profiles = await _profileService.getProfiles(SecurityUtils.activeEnvironment);
      
      setState(() {
        _employees = employees;
        _profiles = profiles;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ImpactToast.show(context, "Errore caricamento dati: $e", isError: true);
      }
    }
  }

  Future<void> _assignProfile(Employment employee, String? profileId) async {
    try {
      await _profileService.assignProfile(
        employeeId: employee.id,
        profileId: profileId,
        companyId: SecurityUtils.activeEnvironment,
      );
      _loadData();
      if (mounted) {
        ImpactToast.show(context, "Profilo aggiornato per ${employee.fullName}");
      }
    } catch (e) {
      if (mounted) {
        ImpactToast.show(context, "Errore salvataggio: $e", isError: true);
      }
    }
  }

  List<Employment> get _filteredEmployees {
    if (_searchQuery.isEmpty) return _employees;
    return _employees.where((e) => 
      e.fullName.toLowerCase().contains(_searchQuery.toLowerCase()) ||
      e.role.toLowerCase().contains(_searchQuery.toLowerCase())
    ).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: const Text("GESTIONE DIPENDENTI"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadData,
          ),
        ],
      ),
      body: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppTheme.background, const Color(0xFF1E1B4B)],
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("Organico & Contratti", style: Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 4),
                          Text(
                            "Assegna i profili normativi ai dipendenti per limitare le ore settimanali.",
                            style: TextStyle(color: AppTheme.textSecondary),
                          ),
                        ],
                      ),
                      Container(
                        width: 300,
                        child: TextField(
                          onChanged: (v) => setState(() => _searchQuery = v),
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            hintText: "Cerca dipendente o ruolo...",
                            hintStyle: TextStyle(color: AppTheme.textSecondary.withOpacity(0.5)),
                            prefixIcon: const Icon(Icons.search, color: AppTheme.aiGlow),
                            filled: true,
                            fillColor: Colors.white.withOpacity(0.05),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),
                  Expanded(
                    child: _isLoading 
                      ? const Center(child: CircularProgressIndicator(color: AppTheme.aiGlow))
                      : _filteredEmployees.isEmpty
                        ? _buildEmptyState()
                        : _buildEmployeesTable(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.people_outline_rounded, size: 64, color: AppTheme.textSecondary.withOpacity(0.2)),
          const SizedBox(height: 16),
          Text("Nessun dipendente trovato", style: TextStyle(color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  Widget _buildEmployeesTable() {
    return Container(
      decoration: AppTheme.glassDecoration(),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: SingleChildScrollView(
          child: DataTable(
            headingRowColor: MaterialStateProperty.all(Colors.white.withOpacity(0.05)),
            columns: const [
              DataColumn(label: Text("DIPENDENTE", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold))),
              DataColumn(label: Text("RUOLO", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold))),
              DataColumn(label: Text("ORE CONTR.", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold))),
              DataColumn(label: Text("PROFILO NORMATIVO", style: TextStyle(color: AppTheme.aiGlow, fontWeight: FontWeight.bold))),
            ],
            rows: _filteredEmployees.map((e) => _buildEmployeeRow(e)).toList(),
          ),
        ),
      ),
    );
  }

  DataRow _buildEmployeeRow(Employment employee) {
    return DataRow(
      cells: [
        DataCell(
          Row(
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: AppTheme.primary.withOpacity(0.2),
                child: Text(employee.fullName[0].toUpperCase(), style: const TextStyle(fontSize: 10, color: AppTheme.primary)),
              ),
              const SizedBox(width: 12),
              Text(employee.fullName, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
            ],
          ),
        ),
        DataCell(Text(employee.role.toUpperCase(), style: TextStyle(color: AppTheme.textSecondary, fontSize: 12))),
        DataCell(Text("${employee.contractHours ?? '--'}h", style: const TextStyle(color: Colors.white))),
        DataCell(
          Container(
            width: 250,
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: employee.laborProfileId,
                hint: Text("Default Aziendale", style: TextStyle(color: AppTheme.textSecondary.withOpacity(0.5), fontSize: 13, fontStyle: FontStyle.italic)),
                isExpanded: true,
                dropdownColor: AppTheme.surface,
                icon: const Icon(Icons.arrow_drop_down, color: AppTheme.textSecondary),
                items: [
                  const DropdownMenuItem<String>(
                    value: null,
                    child: Text("Default Aziendale", style: TextStyle(color: Colors.white70, fontSize: 13, fontStyle: FontStyle.italic)),
                  ),
                  ..._profiles.map((p) => DropdownMenuItem(
                    value: p.id,
                    child: Text(p.name, style: const TextStyle(color: Colors.white, fontSize: 13)),
                  )),
                ],
                onChanged: (v) => _assignProfile(employee, v),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
