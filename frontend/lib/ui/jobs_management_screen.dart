import 'package:flutter/material.dart';
import '../models/agent_models.dart';
import '../models/company_model.dart';
import '../repositories/schedule_repository.dart';

class JobsManagementScreen extends StatefulWidget {
  const JobsManagementScreen({Key? key}) : super(key: key);

  @override
  State<JobsManagementScreen> createState() => _JobsManagementScreenState();
}

class _JobsManagementScreenState extends State<JobsManagementScreen> {
  final ScheduleRepository _repository = ScheduleRepository();
  
  List<Company> _companies = [];
  List<Activity> _activities = [];
  bool _isLoading = true;
  String _searchQuery = '';
  Company? _selectedCompany;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final companies = await _repository.getCompanies();
      final activities = await _repository.getActivities();
      
      setState(() {
        _companies = companies;
        _activities = activities;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Errore caricamento dati: $e')),
        );
      }
    }
  }

  List<Activity> get _filteredActivities {
    var filtered = _activities;
    
    // Filter by selected company
    if (_selectedCompany != null) {
      filtered = filtered.where((activity) {
        final projectCustomer = activity.project?['customer'];
        if (projectCustomer == null) return false;
        final customerId = projectCustomer['id']?.toString() ?? '';
        return customerId == _selectedCompany!.id;
      }).toList();
    }
    
    // Filter by search query
    if (_searchQuery.isNotEmpty) {
      filtered = filtered.where((activity) {
        final name = activity.name.toLowerCase();
        final query = _searchQuery.toLowerCase();
        return name.contains(query);
      }).toList();
    }
    
    return filtered;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E27),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1A1F3A),
        elevation: 0,
        title: const Text(
          'Gestione Commesse',
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF6C5CE7)))
          : Column(
              children: [
                _buildFilters(),
                _buildStats(),
                Expanded(child: _buildJobsList()),
              ],
            ),
    );
  }

  Widget _buildFilters() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          // Search bar
          TextField(
            onChanged: (value) => setState(() => _searchQuery = value),
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'Cerca commessa...',
              hintStyle: TextStyle(color: Colors.white.withOpacity(0.5)),
              prefixIcon: const Icon(Icons.search, color: Color(0xFF6C5CE7)),
              filled: true,
              fillColor: const Color(0xFF0A0E27),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          const SizedBox(height: 12),
          // Company filter
          DropdownButtonFormField<Company>(
            value: _selectedCompany,
            dropdownColor: const Color(0xFF1A1F3A),
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              labelText: 'Filtra per Cliente',
              labelStyle: const TextStyle(color: Color(0xFF6C5CE7)),
              filled: true,
              fillColor: const Color(0xFF0A0E27),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
            items: [
              const DropdownMenuItem<Company>(
                value: null,
                child: Text('Tutti i clienti'),
              ),
              ..._companies.map((company) => DropdownMenuItem<Company>(
                    value: company,
                    child: Text(company.name),
                  )),
            ],
            onChanged: (value) => setState(() => _selectedCompany = value),
          ),
        ],
      ),
    );
  }

  Widget _buildStats() {
    final totalJobs = _filteredActivities.length;
    final uniqueCompanies = _filteredActivities
        .map((a) => a.project?['customer']?['id'])
        .where((id) => id != null)
        .toSet()
        .length;

    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          _buildStatCard(
            icon: Icons.work_outline,
            label: 'Commesse',
            value: totalJobs.toString(),
            color: const Color(0xFF6C5CE7),
          ),
          const SizedBox(width: 12),
          _buildStatCard(
            icon: Icons.business,
            label: 'Clienti',
            value: uniqueCompanies.toString(),
            color: const Color(0xFF00B894),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1F3A),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.7),
                    fontSize: 12,
                  ),
                ),
                Text(
                  value,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildJobsList() {
    if (_filteredActivities.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.work_off,
              size: 64,
              color: Colors.white.withOpacity(0.3),
            ),
            const SizedBox(height: 16),
            Text(
              'Nessuna commessa trovata',
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontSize: 16,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _filteredActivities.length,
      itemBuilder: (context, index) {
        final activity = _filteredActivities[index];
        return _buildJobCard(activity);
      },
    );
  }

  Widget _buildJobCard(Activity activity) {
    final customer = activity.project?['customer'];
    final customerName = customer?['name'] ?? 'Cliente sconosciuto';
    final customerCity = customer?['city'] ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFF6C5CE7).withOpacity(0.3),
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => _showJobDetails(activity),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: const Color(0xFF6C5CE7).withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.work,
                        color: Color(0xFF6C5CE7),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            activity.name,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            customerName,
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.7),
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(
                      Icons.chevron_right,
                      color: Color(0xFF6C5CE7),
                    ),
                  ],
                ),
                if (customerCity.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(
                        Icons.location_on,
                        size: 16,
                        color: Colors.white.withOpacity(0.5),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        customerCity,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.5),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showJobDetails(Activity activity) {
    final customer = activity.project?['customer'];
    
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1A1F3A),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.work, color: Color(0xFF6C5CE7), size: 32),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    activity.name,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildDetailRow('Cliente', customer?['name'] ?? 'N/A'),
            _buildDetailRow('Città', customer?['city'] ?? 'N/A'),
            _buildDetailRow('Indirizzo', customer?['address'] ?? 'N/A'),
            _buildDetailRow('Telefono', customer?['phone'] ?? 'N/A'),
            _buildDetailRow('Email', customer?['mail'] ?? 'N/A'),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6C5CE7),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Chiudi',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontSize: 14,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
