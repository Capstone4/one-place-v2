import React from "react";
import 'semantic-ui-css/semantic.min.css';
import MenuBar from "./MenuBar";
import PageContent from "./editor/PageContent";
import ProjectBar from "./projectPanel/ProjectBar";
import ToolBar from "./toolsPanel/ToolBar";
import './App.css'
class App extends React.Component {

    state = {
        currentProject: {
            'Title': 'No Project Selected',
            'id': 'None'
        }
    }

    updateProject = (projectDict) => {
        this.setState({currentProject: projectDict})
    }

    render() {
        return (
            <div style={{}}>
                <MenuBar updateProject={this.updateProject} currentProject={this.state.currentProject}/>
                <div id="appArea" className="ui bottom attached segment pushable">
                    <ProjectBar currentProject={this.state.currentProject} />
                    <PageContent currentProject={this.state.currentProject}/>
                    <ToolBar />
                </div>
            </div>)
    }
}

export default App;