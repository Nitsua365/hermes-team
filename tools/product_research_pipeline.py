from hermes_tools import delegate_task, write_file
import datetime

def product_research_pipeline(prompt : str):
    tasks = []
    researchers = ('Macro-Research-Analyst', 'Social-Media-Researcher')
    n = datetime.now()

    # 1. Spawn researchers
    for agent_name in researchers:
        tasks.append({
            goal: f'Research the user prompt and give an answer based on your role and expertise',
            context: f'A user made a request for this topic they want to know more about. Here is their query:\n{prompt}',
            toolsets: ['web', 'file', 'browser', 'terminal', 'memory', 'skills'],   # researcher needs web search
            acp_command: 'hermes',
            acp_args: ['--profile', agent_name, 'chat', '-q']
        })
        
    # runs necessary agents in parallel
    research = delegate_task(tasks)

    # parallelize this potentially (this is heavy I/0 Bound)
    for agent_name, research_report in zip(researchers, research):
        write_file(f"{agent_name}-report-{n.strftime("%Y-%m-%d %H:%M:%S")}.md", research_report)

    # 2. Grading
    graders = ('Customer-Base-Expert', 'Product-Store-Optimizer', 'Product-Expert')
    grade_tasks = []
    for grader in graders:
        for report in research:
            grade_tasks.append({
                goal: f'Grade and give feedback on researched products',
                context: f'Researchers searched for a new product, you will grade their product finding based on your skills and expertise. Here is the report:\n{report}',
                toolsets: ['file', 'terminal', 'memory', 'skills'],
                acp_command: 'hermes',
                acp_args: ['--profile', grader, 'chat', '-q']
            })

    grade_results = delegate_task(grade_tasks)

    for grader, result in zip(graders, grade_results):
        write_file(f"{grader}-grade-{n.strftime("%Y-%m-%d %H:%M:%S")}.md", result)

    # summarize result
    summary = delegate_task(
        goal="Perform a lossless (no detail or concept loss) summary of every report and every grading",
        context=f"You will receive the product research reports here:\n{'\n'.join(research)}\n\nYou will receive grades for reports here by analysts:\n{'\n'.join(grade_results)}",
        toolsets=['file', 'memory', 'skills'],
        
    )

    print("Here is the summary: \n", summary)
    write_file(f"summary-{n.strftime("%Y-%m-%d %H:%M:%S")}")