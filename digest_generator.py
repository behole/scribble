import os
import logging
import json
from datetime import datetime, timedelta
import calendar
import markdown
import re

class DigestGenerator:
    """Generates digests, reports, and other outputs from processed content."""
    
    def __init__(self, db_manager, llm_service):
        self.db_manager = db_manager
        self.llm_service = llm_service
        self.output_dir = "digests"
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def generate_weekly_digest(self, end_date=None):
        """Generate a weekly digest up to the specified date."""
        # If no end date provided, use today
        if not end_date:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
        
        # Calculate the start date (7 days before end date)
        start_date = end_date - timedelta(days=7)
        
        # Format dates for database query
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # Get content for the period
        content_items = self.db_manager.get_content_for_period(start_date_str, end_date_str)
        
        # If no recent content, use all available content instead
        if not content_items:
            logging.info(f"No content found for period {start_date_str} to {end_date_str}, using all available content")
            # Get all content (limited to most recent 50 items)
            content_items = self.db_manager.get_all_content(limit=50)
            
            if not content_items:
                logging.info("No content found in the database")
                return None
        
        # Get all tags and tasks for the content
        contents_with_metadata = []
        for item in content_items:
            content_id = item[0]
            
            # Query for file information
            file_id = item[1]
            file_info = self.db_manager.get_file_by_id(file_id)
            
            # Get tags for the content
            tags = self.db_manager.get_tags_for_content(content_id)
            
            content_dict = {
                'content_id': content_id,
                'file_id': file_id,
                'content_type': item[2],
                'content_text': item[3],
                'processed_text': item[4],
                'date_processed': item[6],
                'file_type': file_info[2] if file_info else 'unknown',
                'file_path': file_info[1] if file_info else 'unknown',
                'tags': tags
            }
            
            contents_with_metadata.append(content_dict)
        
        # Use LLM to generate digest
        digest_content = self.llm_service.generate_weekly_digest(
            contents_with_metadata,
            start_date_str,
            end_date_str
        )
        
        if not digest_content:
            logging.error("Failed to generate weekly digest content")
            return None
        
        # Save the digest to the database
        digest_id = self.db_manager.save_digest(
            digest_type="weekly",
            content=digest_content,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        # Create formatted file name
        file_name = f"weekly_digest_{start_date.strftime('%Y-%m-%d')}_to_{end_date.strftime('%Y-%m-%d')}.md"
        file_path = os.path.join(self.output_dir, file_name)
        
        # Format the digest with title and date information
        formatted_digest = f"# Weekly Digest\n\n"
        formatted_digest += f"**Period:** {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}\n\n"
        formatted_digest += digest_content
        
        # Append tags section
        all_tags = []
        for content in contents_with_metadata:
            all_tags.extend(content.get('tags', []))
        
        # Count and sort tags by frequency
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_tags:
            formatted_digest += "\n\n## Top Tags\n\n"
            for tag, count in sorted_tags[:10]:  # Show top 10 tags
                formatted_digest += f"- #{tag} ({count})\n"
        
        # Save the digest to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(formatted_digest)
        
        logging.info(f"Weekly digest saved to {file_path}")
        
        return {
            'digest_id': digest_id,
            'file_path': file_path,
            'content': formatted_digest
        }
    
    def generate_monthly_digest(self, year=None, month=None):
        """Generate a monthly digest for the specified year and month."""
        # If no year/month provided, use last month
        if not year or not month:
            today = datetime.now()
            first_of_month = today.replace(day=1)
            last_month = first_of_month - timedelta(days=1)
            year = last_month.year
            month = last_month.month
        
        # Create start and end dates for the month
        start_date = datetime(year, month, 1)
        # Get the last day of the month
        _, last_day = calendar.monthrange(year, month)
        end_date = datetime(year, month, last_day, 23, 59, 59)
        
        # Format dates for database query
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        # Get weekly digests for the month
        weekly_digests = []
        current_start = start_date
        
        while current_start <= end_date:
            current_end = current_start + timedelta(days=6)
            if current_end > end_date:
                current_end = end_date
            
            # Query for weekly digest
            digest = self.db_manager.get_latest_digest(
                digest_type="weekly"
            )
            
            if digest:
                weekly_digests.append(digest)
            
            # Move to next week
            current_start = current_end + timedelta(days=1)
        
        # Use LLM to analyze trends if we have multiple weekly digests
        if len(weekly_digests) > 1:
            trend_analysis = self.llm_service.analyze_trends(weekly_digests)
        else:
            trend_analysis = "Insufficient data to analyze trends for this month."
        
        # Get all content for the month directly
        content_items = self.db_manager.get_content_for_period(start_date_str, end_date_str)
        
        # Prepare content for digest
        contents_with_metadata = []
        for item in content_items:
            content_id = item[0]
            tags = self.db_manager.get_tags_for_content(content_id)
            
            content_dict = {
                'content_id': content_id,
                'file_id': item[1],
                'content_type': item[2],
                'content_text': item[3],
                'processed_text': item[4],
                'date_processed': item[6],
                'file_type': item[7],
                'file_path': item[8],
                'tags': tags
            }
            
            contents_with_metadata.append(content_dict)
        
        # Use LLM to generate a monthly summary
        month_name = calendar.month_name[month]
        monthly_summary = self.generate_monthly_summary(contents_with_metadata, month_name, year)
        
        # Compile the full monthly digest
        month_year_str = f"{month_name} {year}"
        
        digest_content = f"# Monthly Digest: {month_year_str}\n\n"
        
        # Add monthly summary
        digest_content += "## Monthly Summary\n\n"
        digest_content += monthly_summary + "\n\n"
        
        # Add trend analysis
        digest_content += "## Trends & Patterns\n\n"
        digest_content += trend_analysis + "\n\n"
        
        # Add weekly digest summaries
        if weekly_digests:
            digest_content += "## Weekly Highlights\n\n"
            for i, weekly in enumerate(weekly_digests, 1):
                weekly_start = datetime.fromisoformat(weekly[3])
                weekly_end = datetime.fromisoformat(weekly[4])
                
                digest_content += f"### Week {i}: {weekly_start.strftime('%B %d')} - {weekly_end.strftime('%B %d')}\n\n"
                
                # Extract summary section from weekly digest
                weekly_content = weekly[5]
                summary_match = re.search(r'## Summary\s+(.+?)(?=\n## |$)', weekly_content, re.DOTALL)
                
                if summary_match:
                    digest_content += summary_match.group(1).strip() + "\n\n"
                else:
                    # Just take the first paragraph if no Summary section
                    first_para = weekly_content.split('\n\n')[0]
                    digest_content += first_para + "\n\n"
        
        # Add tag statistics
        all_tags = []
        for content in contents_with_metadata:
            all_tags.extend(content.get('tags', []))
        
        # Count and sort tags by frequency
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_tags:
            digest_content += "## Top Tags\n\n"
            for tag, count in sorted_tags[:15]:  # Show top 15 tags
                digest_content += f"- #{tag} ({count})\n"
        
        # Save the digest to the database
        digest_id = self.db_manager.save_digest(
            digest_type="monthly",
            content=digest_content,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        # Create formatted file name
        file_name = f"monthly_digest_{year}_{month:02d}_{month_name}.md"
        file_path = os.path.join(self.output_dir, file_name)
        
        # Save the digest to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(digest_content)
        
        logging.info(f"Monthly digest saved to {file_path}")
        
        return {
            'digest_id': digest_id,
            'file_path': file_path,
            'content': digest_content
        }
    
    def generate_monthly_summary(self, contents, month_name, year):
        """Generate a monthly summary using LLM."""
        if not contents:
            return "No content available for this month."
        
        # Group content by type
        content_types = {}
        for content in contents:
            content_type = content.get('content_type', 'unknown')
            if content_type not in content_types:
                content_types[content_type] = []
            content_types[content_type].append(content)
        
        # Create a summary of content by type
        summary_parts = []
        summary_parts.append(f"In {month_name} {year}, the following content was processed:")
        
        for content_type, items in content_types.items():
            summary_parts.append(f"- {len(items)} {content_type} items")
        
        # If we have LLM service, use it for more detailed summary
        if self.llm_service:
            # This would call the LLM service for a more detailed summary
            llm_summary = self.llm_service.summarize_content("\n".join(summary_parts))
            if llm_summary:
                return llm_summary
        
        # Fallback to basic summary
        return "\n".join(summary_parts)
    
    def generate_task_list(self, include_completed=False):
        """Generate a comprehensive task list from all content."""
        # Get all tasks
        tasks = self.db_manager.get_tasks(completed=None if include_completed else False)
        
        # If there are no tasks returned, try to query them directly from the database
        if not tasks:
            logging.info("No tasks found with get_tasks method, trying direct database query")
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_manager.db_path)
                cursor = conn.cursor()
                
                # Query to get all incomplete tasks
                cursor.execute("SELECT id, content_id, task_text, completed, due_date, created_date FROM tasks WHERE completed = 0")
                tasks = cursor.fetchall()
                
                conn.close()
                
                if not tasks:
                    logging.info("Still no tasks found after direct query")
                    # Generate an empty task list anyway with a message
                    task_content = "# Task List\n\n"
                    task_content += f"Generated on: {datetime.now().strftime('%B %d, %Y')}\n\n"
                    task_content += "## No Tasks Found\n\n"
                    task_content += "There are currently no tasks in the system.\n"
                    
                    # Create formatted file name
                    file_name = f"task_list_{datetime.now().strftime('%Y-%m-%d')}.md"
                    file_path = os.path.join(self.output_dir, file_name)
                    
                    # Save the task list to file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(task_content)
                    
                    logging.info(f"Empty task list saved to {file_path}")
                    
                    return {
                        'file_path': file_path,
                        'content': task_content
                    }
            except Exception as e:
                logging.error(f"Error during direct task query: {e}")
                return None
        
        # Format the task list
        task_content = "# Task List\n\n"
        task_content += f"Generated on: {datetime.now().strftime('%B %d, %Y')}\n\n"
        
        # Group tasks by status
        active_tasks = [t for t in tasks if not t[3]]  # Not completed
        completed_tasks = [t for t in tasks if t[3]]   # Completed
        
        # Add active tasks
        task_content += "## Active Tasks\n\n"
        if active_tasks:
            for i, task in enumerate(active_tasks, 1):
                task_text = task[2]
                due_date = task[4]
                
                if due_date:
                    due_str = datetime.fromisoformat(due_date).strftime('%B %d, %Y')
                    task_content += f"{i}. {task_text} (Due: {due_str})\n"
                else:
                    task_content += f"{i}. {task_text}\n"
        else:
            task_content += "No active tasks.\n"
        
        # Add completed tasks if requested
        if include_completed and completed_tasks:
            task_content += "\n## Completed Tasks\n\n"
            for i, task in enumerate(completed_tasks, 1):
                task_content += f"{i}. ~~{task[2]}~~\n"
        
        # Create formatted file name
        file_name = f"task_list_{datetime.now().strftime('%Y-%m-%d')}.md"
        file_path = os.path.join(self.output_dir, file_name)
        
        # Save the task list to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        logging.info(f"Task list saved to {file_path}")
        
        return {
            'file_path': file_path,
            'content': task_content
        }
    
    def generate_topic_report(self, tag=None, limit=100):
        """Generate a report focused on a specific tag or topic."""
        if not tag:
            # Get the most used tag if none specified
            all_tags = self.db_manager.get_top_tags(limit=1)
            if not all_tags:
                logging.info("No tags found")
                return None
            
            tag = all_tags[0][0]
        
        # Get content with this tag
        content_items = self.db_manager.get_content_by_tag(tag, limit=limit)
        
        if not content_items:
            logging.info(f"No content found for tag #{tag}")
            return None
        
        # Prepare content for the LLM
        contents_with_metadata = []
        for item in content_items:
            content_id = item[0]
            all_tags = self.db_manager.get_tags_for_content(content_id)
            
            content_dict = {
                'content_id': content_id,
                'file_id': item[1],
                'content_type': item[2],
                'content_text': item[3],
                'processed_text': item[4],
                'date_processed': item[6],
                'file_type': item[7],
                'file_path': item[8],
                'tags': all_tags
            }
            
            contents_with_metadata.append(content_dict)
        
        # Use LLM to generate a topic analysis
        topic_analysis = self.analyze_topic(contents_with_metadata, tag)
        
        # Compile the topic report
        report_content = f"# Topic Report: #{tag}\n\n"
        report_content += f"Generated on: {datetime.now().strftime('%B %d, %Y')}\n\n"
        
        # Add the topic analysis
        report_content += "## Analysis\n\n"
        report_content += topic_analysis + "\n\n"
        
        # Add a list of related content
        report_content += "## Related Content\n\n"
        for content in contents_with_metadata[:10]:  # Limit to top 10
            file_path = content.get('file_path', '')
            filename = os.path.basename(file_path)
            date = datetime.fromisoformat(content.get('date_processed', '')).strftime('%B %d, %Y')
            
            report_content += f"- {filename} ({date})\n"
        
        # Add related tags
        related_tags = self.db_manager.get_related_tags(tag, limit=10)
        if related_tags:
            report_content += "\n## Related Tags\n\n"
            for rel_tag, count in related_tags:
                report_content += f"- #{rel_tag} ({count})\n"
        
        # Create formatted file name
        file_name = f"topic_report_{tag}_{datetime.now().strftime('%Y-%m-%d')}.md"
        file_path = os.path.join(self.output_dir, file_name)
        
        # Save the report to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logging.info(f"Topic report saved to {file_path}")
        
        return {
            'file_path': file_path,
            'content': report_content
        }
    
    def analyze_topic(self, contents, tag):
        """Analyze content related to a specific topic/tag."""
        if not contents:
            return "No content available for this topic."
        
        # Extract snippets from content for analysis
        snippets = []
        for content in contents[:5]:  # Limit to first 5 items
            text = content.get('processed_text') or content.get('content_text', '')
            if text:
                # Extract a snippet (first 200 chars)
                snippet = text[:200] + "..."
                snippets.append(snippet)
        
        # Basic analysis
        analysis = f"Analysis of content tagged with #{tag}:\n\n"
        analysis += f"- {len(contents)} items found with this tag\n"
        analysis += f"- Content types include: {', '.join(set(c.get('content_type', 'unknown') for c in contents))}\n"
        
        # If we have LLM service, use it for more detailed analysis
        if self.llm_service and snippets:
            combined_text = "\n\n---\n\n".join(snippets)
            prompt = f"Please analyze the following content snippets related to the topic '{tag}':\n\n{combined_text}"
            
            llm_analysis = self.llm_service.summarize_content(prompt)
            if llm_analysis:
                return llm_analysis
        
        # Fallback to basic analysis
        return analysis
    
    def generate_suggested_reading(self, limit=5):
        """Generate suggested reading based on recent content interests."""
        # Get recent content (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        content_items = self.db_manager.get_content_for_period(
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        if not content_items:
            logging.info("No recent content found for suggested reading")
            return None
        
        # Prepare content for the LLM
        contents_with_metadata = []
        for item in content_items:
            content_id = item[0]
            tags = self.db_manager.get_tags_for_content(content_id)
            
            content_dict = {
                'content_id': content_id,
                'content_type': item[2],
                'content_text': item[3],
                'processed_text': item[4],
                'tags': tags
            }
            
            contents_with_metadata.append(content_dict)
        
        # Use LLM to generate suggestions
        suggestions = self.llm_service.suggest_reading(contents_with_metadata, num_items=limit)
        
        if not suggestions:
            logging.error("Failed to generate reading suggestions")
            return None
        
        # Compile the suggestions
        report_content = f"# Suggested Reading\n\n"
        report_content += f"Generated on: {datetime.now().strftime('%B %d, %Y')}\n\n"
        report_content += "Based on your recent interests, here are some recommended resources:\n\n"
        report_content += suggestions
        
        # Create formatted file name
        file_name = f"suggested_reading_{datetime.now().strftime('%Y-%m-%d')}.md"
        file_path = os.path.join(self.output_dir, file_name)
        
        # Save the suggestions to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logging.info(f"Suggested reading saved to {file_path}")
        
        return {
            'file_path': file_path,
            'content': report_content
        }
    
    def generate_full_digest(self):
        """Generate a comprehensive digest of all content."""
        # Get all weekly digests
        all_digests = self.db_manager.get_all_digests(digest_type="weekly")
        
        if not all_digests:
            logging.info("No weekly digests found for full digest")
            return None
        
        # Sort digests by date
        sorted_digests = sorted(all_digests, key=lambda d: datetime.fromisoformat(d[3]))  # Sort by start_date
        
        # Compile the full digest
        full_digest_content = f"# Full Digest\n\n"
        full_digest_content += f"Generated on: {datetime.now().strftime('%B %d, %Y')}\n\n"
        
        # Add a table of contents
        full_digest_content += "## Table of Contents\n\n"
        
        for i, digest in enumerate(sorted_digests, 1):
            start_date = datetime.fromisoformat(digest[3]).strftime('%B %d, %Y')
            end_date = datetime.fromisoformat(digest[4]).strftime('%B %d, %Y')
            full_digest_content += f"{i}. [Week {i}: {start_date} - {end_date}](#week-{i})\n"
        
        # Add each digest
        for i, digest in enumerate(sorted_digests, 1):
            start_date = datetime.fromisoformat(digest[3]).strftime('%B %d, %Y')
            end_date = datetime.fromisoformat(digest[4]).strftime('%B %d, %Y')
            
            full_digest_content += f"\n## Week {i}: {start_date} - {end_date} <a id=\"week-{i}\"></a>\n\n"
            full_digest_content += digest[5]  # Content
            full_digest_content += "\n\n---\n\n"
        
        # Create formatted file name
        file_name = f"full_digest_{datetime.now().strftime('%Y-%m-%d')}.md"
        file_path = os.path.join(self.output_dir, file_name)
        
        # Save the full digest to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_digest_content)
        
        logging.info(f"Full digest saved to {file_path}")
        
        return {
            'file_path': file_path,
            'content': full_digest_content
        }

# Example usage
if __name__ == "__main__":
    from database_manager import DatabaseManager
    from llm_service import LLMService
    
    # Initialize the services
    db_manager = DatabaseManager("test_notes.db")
    llm_service = LLMService()
    
    # Initialize the digest generator
    digest_generator = DigestGenerator(db_manager, llm_service)
    
    # Generate a weekly digest
    weekly_digest = digest_generator.generate_weekly_digest()
    if weekly_digest:
        print(f"Weekly digest generated: {weekly_digest['file_path']}")
    
    # Generate a task list
    task_list = digest_generator.generate_task_list()
    if task_list:
        print(f"Task list generated: {task_list['file_path']}")