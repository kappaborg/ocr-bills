import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// Primary CTA with the website's signature cyan→emerald gradient and dark
/// text. Use for the single most important action on a screen (Sign In,
/// Confirm Receipt, Upgrade); use FilledButton/OutlinedButton for the rest.
class GradientButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final Widget child;
  final Widget? icon;
  final double height;

  const GradientButton({
    super.key,
    required this.onPressed,
    required this.child,
    this.icon,
    this.height = 48,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          gradient: Brand.ctaGradient,
          borderRadius: BorderRadius.circular(12),
          boxShadow: enabled
              ? [
                  BoxShadow(
                    color: Brand.cyan.withValues(alpha: 0.25),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ]
              : null,
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onPressed,
            borderRadius: BorderRadius.circular(12),
            child: Center(
              child: DefaultTextStyle(
                style: const TextStyle(
                  color: Brand.slate950,
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                ),
                child: IconTheme(
                  data: const IconThemeData(color: Brand.slate950, size: 20),
                  child: icon == null
                      ? child
                      : Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [icon!, const SizedBox(width: 8), child],
                        ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Tiny uppercase wide-tracked section label — the web uses this above every
/// page title ("OVERVIEW", "REVIEW", "STEP 1 OF 3").
class SectionLabel extends StatelessWidget {
  final String text;
  const SectionLabel(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        letterSpacing: 3.0,
        color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.9),
      ),
    );
  }
}

/// Amount text with the brand's mono + tabular numerals treatment.
class MoneyText extends StatelessWidget {
  final String text;
  final double fontSize;
  final Color? color;
  const MoneyText(this.text, {super.key, this.fontSize = 16, this.color});

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: AppTheme.moneyStyle.copyWith(
        fontSize: fontSize,
        color: color ?? Theme.of(context).colorScheme.onSurface,
      ),
    );
  }
}
