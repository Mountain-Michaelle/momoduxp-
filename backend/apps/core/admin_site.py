"""
Custom Django Admin Site for Momodu SaaS.
Dark Indigo Theme with enhanced features.
"""

from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponse



class MomoduAdminSite(AdminSite):
    """
    Custom admin site with Dark Indigo theme.
    """

    # Site header - shown at top of admin
    site_header = "Momodu SP Administration"
    site_title = "Momodu Admin Portal"
    index_title = "Dashboard Overview"

    # Enable custom stylesheet
    enable_nav_sidebar = True

    def get_urls(self):
        """Add custom URLs for admin dashboard."""
        urls = super().get_urls()

        # Add custom dashboard stats view
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]

        return custom_urls + urls

    def dashboard_view(self, request):
        """
        Custom dashboard with statistics overview.
        """
        from django.contrib.auth.models import User
        from apps.accounts.models import SocialPlatformAccount, UsageQuota
        from apps.posts.models import ScheduledPost, PostStatus
        from apps.webhooks.models import WebhookEndpoint, WebhookDelivery

        # Get statistics
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'pro_users': User.objects.filter(subscription_plan='pro').count(),
            'total_accounts': SocialPlatformAccount.objects.count(),
            'total_posts': ScheduledPost.objects.count(),
            'published_posts': ScheduledPost.objects.filter(status='published').count(),
            'draft_posts': ScheduledPost.objects.filter(status='draft').count(),
            'pending_approval': ScheduledPost.objects.filter(status='sent_for_approval').count(),
            'total_webhooks': WebhookEndpoint.objects.count(),
            'active_webhooks': WebhookEndpoint.objects.filter(is_active=True).count(),
            'successful_deliveries': WebhookDelivery.objects.filter(succeeded=True).count(),
            'failed_deliveries': WebhookDelivery.objects.filter(succeeded=False).count(),
        }

        # Recent activity
        recent_users = User.objects.order_by('-created_at')[:5]
        recent_posts = ScheduledPost.objects.order_by('-created_at')[:5]

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Momodu Dashboard</title>
            <style>
                :root {{
                    --indigo-600: #4f46e5;
                    --indigo-700: #4338ca;
                    --indigo-800: #3730a3;
                    --vscode-bg: #1e1e2e;
                    --vscode-bg-secondary: #282838;
                    --vscode-bg-hover: #323244;
                    --vscode-text: #cdd6f4;
                    --vscode-text-bright: #f5f5f5;
                    --vscode-border: #3f3f56;
                    --vscode-green: #a3e635;
                    --vscode-orange: #fbbf24;
                    --vscode-red: #f87171;
                    --vscode-grey: #a1a1aa;
                }}

                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background-color: var(--vscode-bg);
                    color: var(--vscode-text);
                    margin: 0;
                    padding: 20px;
                }}

                .dashboard-container {{
                    max-width: 1400px;
                    margin: 0 auto;
                }}

                h1, h2, h3 {{
                    color: var(--vscode-text-bright);
                }}

                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid var(--vscode-border);
                }}

                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}

                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}

                .stat-card {{
                    background-color: var(--vscode-bg-secondary);
                    border: 1px solid var(--vscode-border);
                    border-radius: 8px;
                    padding: 20px;
                    transition: transform 0.2s, box-shadow 0.2s;
                }}

                .stat-card:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
                }}

                .stat-label {{
                    font-size: 12px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 8px;
                    color: var(--vscode-grey);
                }}

                .stat-value {{
                    font-size: 32px;
                    font-weight: bold;
                    color: var(--vscode-text-bright);
                }}

                .stat-card.indigo {{ border-left: 4px solid var(--indigo-600); }}
                .stat-card.green {{ border-left: 4px solid var(--vscode-green); }}
                .stat-card.orange {{ border-left: 4px solid var(--vscode-orange); }}
                .stat-card.red {{ border-left: 4px solid var(--vscode-red); }}

                .section {{
                    background-color: var(--vscode-bg-secondary);
                    border: 1px solid var(--vscode-border);
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}

                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid var(--vscode-border);
                }}

                th {{
                    color: var(--vscode-text-bright);
                    font-weight: 600;
                    background-color: var(--vscode-bg);
                }}

                tr:hover {{
                    background-color: rgba(79, 70, 229, 0.1);
                }}

                .status-badge {{
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                }}

                .status-draft {{ background-color: #9e9e9e; color: white; }}
                .status-sent {{ background-color: #ff9800; color: white; }}
                .status-approved {{ background-color: var(--vscode-green); color: white; }}
                .status-published {{ background-color: var(--indigo-600); color: white; }}
                .status-failed {{ background-color: var(--vscode-red); color: white; }}

                .quick-actions {{
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }}

                .quick-action {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: var(--indigo-600);
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 500;
                    transition: all 0.2s;
                }}

                .quick-action:hover {{
                    background-color: var(--indigo-500);
                    transform: translateY(-1px);
                    color: white;
                }}

                .quick-action.green {{ background-color: var(--vscode-green); }}
                .quick-action.green:hover {{ background-color: #84cc16; }}
            </style>
        </head>
        <body>
            <div class="dashboard-container">
                <div class="header">
                    <h1>📊 Momodu SaaS Dashboard</h1>
                    <div class="quick-actions">
                        <a href="/admin/accounts/user/add/" class="quick-action green">+ New User</a>
                        <a href="/admin/posts/scheduledpost/add/" class="quick-action">+ New Post</a>
                        <a href="/admin/webhooks/webhookendpoint/add/" class="quick-action">+ New Webhook</a>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card indigo">
                        <div class="stat-label">Total Users</div>
                        <div class="stat-value">{stats['total_users']}</div>
                    </div>
                    <div class="stat-card green">
                        <div class="stat-label">Active Users</div>
                        <div class="stat-value">{stats['active_users']}</div>
                    </div>
                    <div class="stat-card orange">
                        <div class="stat-label">Pro Users</div>
                        <div class="stat-value">{stats['pro_users']}</div>
                    </div>
                    <div class="stat-card indigo">
                        <div class="stat-label">Social Accounts</div>
                        <div class="stat-value">{stats['total_accounts']}</div>
                    </div>
                    <div class="stat-card green">
                        <div class="stat-label">Published Posts</div>
                        <div class="stat-value">{stats['published_posts']}</div>
                    </div>
                    <div class="stat-card orange">
                        <div class="stat-label">Pending Approval</div>
                        <div class="stat-value">{stats['pending_approval']}</div>
                    </div>
                    <div class="stat-card red">
                        <div class="stat-label">Failed Posts</div>
                        <div class="stat-value">{stats['draft_posts'] - stats['published_posts'] - stats['pending_approval']}</div>
                    </div>
                    <div class="stat-card indigo">
                        <div class="stat-label">Active Webhooks</div>
                        <div class="stat-value">{stats['active_webhooks']}</div>
                    </div>
                </div>

                <div class="section">
                    <h2>📝 Recent Posts</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Content Preview</th>
                                <th>Author</th>
                                <th>Platform</th>
                                <th>Status</th>
                                <th>Scheduled</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        for post in recent_posts:
            status_class = f"status-{post.status}"
            content_preview = post.content[:50] + '...' if len(post.content) > 50 else post.content
            html += f"""
                            <tr>
                                <td>{content_preview}</td>
                                <td>{post.author.email}</td>
                                <td>{post.account.platform}</td>
                                <td><span class="status-badge {status_class}">{post.get_status_display()}</span></td>
                                <td>{post.scheduled_for.strftime('%Y-%m-%d %H:%M')}</td>
                            </tr>
            """

        html += """
                        </tbody>
                    </table>
                </div>

                <div class="section">
                    <h2>👥 Recent Users</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Email</th>
                                <th>Username</th>
                                <th>Plan</th>
                                <th>Status</th>
                                <th>Joined</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        for user in recent_users:
            plan_color = 'var(--indigo-600)' if user.subscription_plan == 'free' else 'var(--vscode-green)' if user.subscription_plan == 'pro' else 'var(--vscode-orange)'
            status_color = 'var(--vscode-green)' if user.is_active else 'var(--vscode-red)'
            html += f"""
                            <tr>
                                <td>{user.email}</td>
                                <td>{user.username}</td>
                                <td><span style="color: {plan_color};">{user.subscription_plan.upper()}</span></td>
                                <td><span style="color: {status_color};">{'Active' if user.is_active else 'Inactive'}</span></td>
                                <td>{user.created_at.strftime('%Y-%m-%d')}</td>
                            </tr>
            """

        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
        """

        return HttpResponse(html)


# Create custom admin site instance
momodu_admin_site = MomoduAdminSite(name='momodu_admin')

# Register models with custom admin site
# Note: You'll need to import and register models with momodu_admin_site
# Example: momodu_admin_site.register(User, UserAdmin)
