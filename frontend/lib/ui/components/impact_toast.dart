import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ImpactToast extends StatelessWidget {
  final String message;
  final bool isVisible;

  const ImpactToast({
    super.key,
    required this.message,
    required this.isVisible,
  });

  @override
  Widget build(BuildContext context) {
    return const SizedBox.shrink(); // This widget is mainly used via the static show() method
  }

  static void show(BuildContext context, String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        behavior: SnackBarBehavior.floating,
        content: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.surface.withOpacity(0.9),
              borderRadius: BorderRadius.circular(30),
              border: Border.all(
                color: (isError ? Colors.redAccent : AppTheme.aiGlow).withOpacity(0.5), 
                width: 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: (isError ? Colors.redAccent : AppTheme.aiGlow).withOpacity(0.2),
                  blurRadius: 20,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isError ? Icons.error_outline_rounded : Icons.auto_awesome, 
                  color: isError ? Colors.redAccent : AppTheme.aiGlow, 
                  size: 20,
                ),
                const SizedBox(width: 12),
                Text(
                  message,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
